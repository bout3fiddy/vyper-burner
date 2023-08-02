import json
import os
import pprint
import warnings
from typing import Dict, List, Tuple

import ape
import requests
from ape.logging import logger

warnings.filterwarnings("ignore")

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONVEX_VOTERPROXY = "0x989AEB4D175E16225E39E87D0D97A3360524AD80"
CURVE_DAO_OWNERSHIP = {
    "agent": "0x40907540d8a6c65c637785e8f8b742ae6b0b9968",
    "voting": "0xe478de485ad2fe566d49342cbd03e49ed7db3356",
    "token": "0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2",
    "quorum": 30,
}
BOSS = {
    "ethereum": "0xEdf2C58E16Cc606Da1977e79E1e69e79C54fe242",
    "arbitrum": "0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
    "optimism": "0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
    "polygon": "0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
    "gnosis": "0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
}
FIDDY = "0xE6DA683076b7eD6ce7eC972f21Eb8F91e9137a17"


def get_tx_params():

    if "mainnet-fork" == ape.networks.active_provider.network.name:
        return {
            "gas_price": 0,
            "gas_limit": 450000,
        }

    if "sepolia" == ape.networks.active_provider.network.name:
        return {}

    active_provider = ape.networks.active_provider
    max_fee = int(active_provider.base_fee * 1.2)
    max_priority_fee = int(0.5e9)

    return {
        "max_fee": max_fee,
        "max_priority_fee": max_priority_fee,
    }


def prepare_evm_script(target: Dict, actions: List[Tuple]) -> str:
    """Generates EVM script to be executed by AragonDAO contracts.

    Args:
        target (dict): CURVE_DAO_OWNERSHIP / CURVE_DAO_PARAMS / EMERGENCY_DAO
        actions (list(tuple)): ("target addr", "fn_name", *args)

    Returns:
        str: Generated EVM script.
    """
    agent = ape.Contract(target["agent"])
    voting = target["voting"]

    logger.info(f"Agent Contract: {agent.address}")
    logger.info(f"Voting Contract: {voting}")

    evm_script = "0x00000001"

    for address, fn_name, *args in actions:

        contract = ape.Contract(address)
        fn = getattr(contract, fn_name)
        calldata = fn.as_transaction(
            *args, sender=agent.address, gas_price=0
        ).data
        agent_calldata = agent.execute.as_transaction(
            address, 0, calldata, sender=voting, gas_price=0
        ).data
        length = hex(len(agent_calldata.hex()) // 2)[2:].zfill(8)
        evm_script = (
            f"{evm_script}{agent.address[2:]}{length}{agent_calldata.hex()}"
        )

    return evm_script


def get_vote_description_ipfs_hash(description: str):
    """Uploads vote description to IPFS and returns the IPFS hash.

    NOTE: needs environment variables for infura IPFS access. Please
    set up an IPFS project to generate project id and project secret!
    """
    text = json.dumps({"text": description})
    response = requests.post(
        "https://ipfs.infura.io:5001/api/v0/add",
        files={"file": text},
        auth=(os.getenv("IPFS_PROJECT_ID"), os.getenv("IPFS_PROJECT_SECRET")),
    )
    return response.json()["Hash"]


def make_vote(
    target: Dict, actions: List[Tuple], description: str, vote_creator: str
):
    """Prepares EVM script and creates an on-chain AragonDAO vote.

    Args:
        target (dict): ownership / parameter / emergency
        actions (list(tuple)): ("target addr", "fn_name", *args)
        vote_creator (str): msg.sender address
        description (str): Description of the on-chain governance proposal

    Returns:
        str: vote ID of the created vote.
    """
    aragon = ape.Contract(target["voting"])
    assert aragon.canCreateNewVote(
        vote_creator
    ), "dev: user cannot create new vote"

    evm_script = prepare_evm_script(target, actions)
    logger.debug(f"EVM script: {evm_script}")

    tx = aragon.newVote(
        evm_script,
        f"ipfs:{get_vote_description_ipfs_hash(description)}",
        False,
        False,
        sender=vote_creator,
    )
    return tx.events[0].voteId


def simulate(vote_ids: List[int], voting_contract: str):
    """Simulate passing vote on mainnet-fork"""
    logger.info("--------- SIMULATE VOTE ---------")

    try:
        aragon = ape.Contract(voting_contract)
    except:
        breakpoint()

    # vote
    logger.info("Simulate Convex 'yes' vote")
    for _vote_id in vote_ids:

        # print vote details to console first:
        logger.info(f"Vote stats before Convex Vote for vote id {_vote_id}:")
        vote_stats = aragon.getVote(_vote_id)
        logger.info(pprint.pformat(vote_stats, indent=4))

        # Vote:
        aragon.vote(
            _vote_id,
            True,
            False,
            sender=ape.accounts[CONVEX_VOTERPROXY],
            gas_price=0,
        )

    # sleep for a week so it has time to pass
    num_blocks = int(aragon.voteTime() + 200 / 10)
    ape.chain.mine(num_blocks)

    # moment of truth - execute the vote!
    logger.info("Simulate proposal execution")
    for _vote_id in vote_ids:
        aragon.executeVote(_vote_id, sender=ape.accounts[CONVEX_VOTERPROXY])
    logger.info("Vote Executed!")
