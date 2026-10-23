# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
class _PayoutDeposit:

    def __init__(self, address: Address, value: u256):
        self.address = address
        self.value = value

    def deposit(self, withdrawal_id: u256, beneficiary: Address) -> None:
        from genlayer.gl._internal.gl_call import gl_call_generic
        encoder = gl.evm.MethodEncoder('deposit', (u256, Address), type(None))
        gl_call_generic({'EthSend': {'address': self.address, 'calldata': encoder.encode_call((withdrawal_id, beneficiary)), 'value': self.value}}, lambda raw: None).get()
class _PayoutVault:
    """Typed adapter for the pinned runner's EthCall/EthSend host interface.

    Its generated EVM proxy has incompatible view-parent and send-value handling.
    MethodEncoder/decode and the host requests are the pinned SDK's own ABI path.
    """

    def __init__(self, address: Address):
        self.address = address

    def view(self):
        return self

    def _read(self, name, params, result, args):
        from genlayer.gl._internal.gl_call import gl_call_generic
        encoder = gl.evm.MethodEncoder(name, params, result)
        return gl_call_generic({'EthCall': {'address': self.address, 'calldata': encoder.encode_call(args)}}, lambda raw: gl.evm.decode(result, raw)).get()

    def controller(self) -> Address:
        return self._read('controller', (), Address, ())

    def amountOf(self, withdrawal_id: u256) -> u256:
        return self._read('amountOf', (u256,), u256, (withdrawal_id,))

    def beneficiaryOf(self, withdrawal_id: u256) -> Address:
        return self._read('beneficiaryOf', (u256,), Address, (withdrawal_id,))

    def emit(self, *, value: u256):
        return _PayoutDeposit(self.address, value)
class AdapterProbe(gl.Contract):
    controller: str
    amount: u256
    beneficiary: str
    def __init__(self):
        vault=_PayoutVault(Address("0x725b9bbd5665e7aa722e915ae29ee427f4213cb1"))
        self.controller=vault.view().controller().as_hex
        if self.controller.lower() != "0x764fb8e341a1956bcd7cf0bce3c28c79dc694f8c":
            raise gl.vm.UserError("wrong controller")
        self.amount=int(vault.view().amountOf(u256(42)))
        self.beneficiary=vault.view().beneficiaryOf(u256(42)).as_hex
        if self.amount != 0 or self.beneficiary != "0x"+"00"*20:
            raise gl.vm.UserError("unexpected receipt")
        vault.emit(value=u256(1000)).deposit(u256(42),gl.message.sender_address)
