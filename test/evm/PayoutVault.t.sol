// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import "../../contracts/HearsayPayoutVault.sol";

interface Vm {
    function deal(address who, uint256 amount) external;
    function prank(address who) external;
}

contract RefusesGEN {
    receive() external payable { revert("no GEN"); }
}

contract Reenters {
    HearsayPayoutVault public vault;
    uint256 public received;
    bool public reentrySucceeded;
    constructor(HearsayPayoutVault v) { vault = v; }
    function claim() external { vault.claim(payable(address(this))); }
    receive() external payable {
        received += msg.value;
        (reentrySucceeded,) = address(vault).call(abi.encodeCall(vault.claim, (payable(address(this)))));
    }
}

contract PayoutVaultTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    HearsayPayoutVault vault;
    address constant IC = address(0x1234);
    address constant ALICE = address(0x5678);
    address payable constant WORKING = payable(address(0xABCD));

    function setUp() public {
        vault = new HearsayPayoutVault();
        vault.bindController(IC);
        vm.deal(IC, 100 ether);
    }

    function fund(uint256 id, address beneficiary, uint256 amount) internal {
        vm.prank(IC);
        vault.deposit{value: amount}(id, beneficiary);
    }

    function testDeliveryFailurePreservesClaimAndCanRedirect() public {
        fund(0, ALICE, 3 ether);
        RefusesGEN bad = new RefusesGEN();
        vm.prank(ALICE);
        (bool ok,) = address(vault).call(abi.encodeCall(vault.claim, (payable(address(bad)))));
        require(!ok, "delivery must fail");
        require(vault.credit(ALICE) == 3 ether && vault.totalCredit() == 3 ether, "claim lost");
        require(address(vault).balance == 3 ether, "custody lost");
        vm.prank(ALICE);
        vault.claim(WORKING);
        require(WORKING.balance == 3 ether && vault.credit(ALICE) == 0, "retry failed");
        require(vault.amountOf(0) == 3 ether, "receipt must survive claim");
    }

    function testDuplicateDepositCannotDoublePayOrSpendValue() public {
        fund(0, ALICE, 3 ether);
        uint256 beforeBalance = IC.balance;
        vm.prank(IC);
        (bool ok,) = address(vault).call{value: 3 ether}(abi.encodeCall(vault.deposit, (0, ALICE)));
        require(!ok && IC.balance == beforeBalance, "duplicate spent GEN");
        require(vault.credit(ALICE) == 3 ether, "duplicate credit");
    }

    function testUnrelatedSenderCannotFundOrRebind() public {
        vm.deal(ALICE, 1 ether);
        vm.prank(ALICE);
        (bool ok,) = address(vault).call{value: 1 ether}(abi.encodeCall(vault.deposit, (1, ALICE)));
        require(!ok, "foreign sender funded");
        (ok,) = address(vault).call(abi.encodeCall(vault.bindController, (ALICE)));
        require(!ok && vault.controller() == IC, "controller changed");
    }

    function testRecipientCannotReenterForAnotherPayout() public {
        Reenters receiver = new Reenters(vault);
        fund(0, address(receiver), 3 ether);
        receiver.claim();
        require(receiver.received() == 3 ether && !receiver.reentrySucceeded(), "reentry paid");
        require(vault.credit(address(receiver)) == 0 && vault.totalCredit() == 0, "bad accounting");
    }

    function testOtherBeneficiaryFundsRemainAvailable() public {
        fund(0, ALICE, 3 ether);
        fund(1, WORKING, 2 ether);
        RefusesGEN bad = new RefusesGEN();
        vm.prank(ALICE);
        (bool ok,) = address(vault).call(abi.encodeCall(vault.claim, (payable(address(bad)))));
        require(!ok, "expected refusal");
        vm.prank(WORKING);
        vault.claim(WORKING);
        require(WORKING.balance == 2 ether && vault.credit(ALICE) == 3 ether, "other credit lost");
        require(address(vault).balance == vault.totalCredit(), "insolvent");
    }
}
