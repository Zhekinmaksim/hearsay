// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/// @notice Pull-payment custody for finalized Hearsay withdrawals.
/// Deploy once, bind to the new IC once, and verify both addresses publicly.
/// The controller never invokes beneficiary code while funding a claim.
contract HearsayPayoutVault {
    address public immutable binder;
    address public controller;
    mapping(uint256 => uint256) public amountOf;
    mapping(uint256 => address) public beneficiaryOf;
    mapping(address => uint256) public credit;
    uint256 public totalCredit;
    bool private entered;

    event ControllerBound(address indexed controller);
    event Funded(uint256 indexed withdrawalId, address indexed beneficiary, uint256 amount);
    event Paid(address indexed beneficiary, address indexed recipient, uint256 amount);

    constructor() { binder = msg.sender; }

    function bindController(address ic) external {
        require(msg.sender == binder && controller == address(0) && ic != address(0), "binding denied");
        controller = ic;
        emit ControllerBound(ic);
    }

    function deposit(uint256 withdrawalId, address beneficiary) external payable {
        require(msg.sender == controller, "only controller");
        require(beneficiary != address(0) && msg.value > 0, "invalid deposit");
        require(amountOf[withdrawalId] == 0, "already funded");
        amountOf[withdrawalId] = msg.value;
        beneficiaryOf[withdrawalId] = beneficiary;
        credit[beneficiary] += msg.value;
        totalCredit += msg.value;
        emit Funded(withdrawalId, beneficiary, msg.value);
    }

    /// @notice A beneficiary may choose a working recipient after a failed call.
    /// Revert restores the credit and value atomically on any delivery failure.
    function claim(address payable recipient) external {
        require(!entered, "reentrant claim");
        require(recipient != address(0), "zero recipient");
        uint256 amount = credit[msg.sender];
        require(amount > 0, "nothing to claim");
        entered = true;
        credit[msg.sender] = 0;
        totalCredit -= amount;
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "delivery failed");
        entered = false;
        emit Paid(msg.sender, recipient, amount);
    }
}
