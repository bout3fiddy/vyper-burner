import click
from ape import Contract, accounts, networks, project
from ape.cli import NetworkBoundCommand, account_option, network_option

from scripts.vote_utils import CURVE_DAO_OWNERSHIP, make_vote, simulate


def _get_tx_params():

    if "mainnet-fork" == networks.active_provider.network.name:
        return {}

    if "sepolia" == networks.active_provider.network.name:
        return {}

    active_provider = networks.active_provider
    max_fee = int(active_provider.base_fee * 1.2)
    max_priority_fee = int(0.5e9)

    return {"max_fee": max_fee, "max_priority_fee": max_priority_fee}



@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_burner(network, account):
    
    is_sim = "mainnet-fork" in network

    with accounts.use_sender(account) as account:
        
        if is_sim:
            account.balance += int(1e19)
        
        burner_contract = account.deploy(project.VyperBurner)
        print("Created burner contract >", burner_contract)


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_vote(network, account):
    
    TARGET = CURVE_DAO_OWNERSHIP
    PROXY = "0xecb456ea5365865ebab8a2661b0c503410e9b347"
    CRV_TOKEN = "0xD533a949740bb3306d119CC777fa900bA034cd52"
    DESCRIPTION = "Set VyperBurner (funds Vyper Security) for CRV earned by the DAO"
    VYPER = "0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775"
    burner_contract = Contract("0x06452f9c013fc37169B57Eab8F50A7A48c9198A3")
    is_sim = "mainnet-fork" in network
    
    if is_sim:
        account = accounts["0x7a16fF8270133F063aAb6C9977183D9e72835428"]
    
    with accounts.use_sender(account) as account:
        
        if is_sim:
            account.balance += int(1e19)
        
        burner_contract = account.deploy(project.VyperBurner)
        
        ACTIONS = [(PROXY, 'set_burner', CRV_TOKEN, burner_contract)]
        ACTIONS = [
            (
                "0xecb456ea5365865ebab8a2661b0c503410e9b347",
                "set_burner",
                "0xD533a949740bb3306d119CC777fa900bA034cd52",
                "0x06452f9c013fc37169B57Eab8F50A7A48c9198A3"
            )
        ]
        
        vote_id = make_vote(TARGET, ACTIONS, DESCRIPTION, account)
        print("created vote!")
        
        # ----- simulate vote outcome ----

        if is_sim:
            simulate([vote_id], TARGET["voting"])
            assert Contract(PROXY).burners(CRV_TOKEN) == burner_contract
            
            CRV = Contract(CRV_TOKEN)
            assert CRV.balanceOf(account) > 10**18
            CRV.transfer(burner_contract, 10**18)
            
            vyper_crv_bal = CRV.balanceOf(VYPER)
            assert CRV.balanceOf(burner_contract) == 10**18
            burner_contract.burn()
            assert CRV.balanceOf(VYPER) - vyper_crv_bal == 10**18     
