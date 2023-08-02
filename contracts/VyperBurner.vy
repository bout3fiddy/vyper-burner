# @version 0.3.9
"""
@title VyperCRVBurner
@author FiddyResearch
@notice Sends CRV tokens earned by CurveDAO from swaps etc.
        to vyperlang.eth multisig.
"""

from vyper.interfaces import ERC20


CRV: constant(address) = 0xD533a949740bb3306d119CC777fa900bA034cd52
MULTISIG: constant(address) = 0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775
PROXY: constant(address) = 0xeCb456EA5365865EbAb8a2661B0c503410e9B347


@external
def burn() -> bool:

    amount: uint256 = ERC20(CRV).balanceOf(self)
    if amount != 0:
        ERC20(CRV).transfer(MULTISIG, amount)

    return True


@external
def recover_erc20(_coin: ERC20):
    amount: uint256 = _coin.balanceOf(self)
    _coin.transfer(PROXY, amount)
