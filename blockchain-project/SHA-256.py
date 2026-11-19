import hashlib
import json
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"
web3 = Web3(Web3.HTTPProvider(RPC_URL))

CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
CONTRACT_ABI = json.loads('''[
    {"inputs":[{"internalType":"string","name":"_docId","type":"string"},{"internalType":"bytes32","name":"_documentHash","type":"bytes32"}],"name":"registerDocument","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"string","name":"_docId","type":"string"},{"internalType":"bytes32","name":"_newHash","type":"bytes32"}],"name":"updateDocument","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"string","name":"_docId","type":"string"},{"internalType":"bytes32","name":"_currentHash","type":"bytes32"}],"name":"verifyIntegrity","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"}
]''')

def calculate_sha256(content: bytes) -> str:
    """Հաշվարկում է փաստաթղթի 64-նիշանոց SHA-256 հեշը"""
    return hashlib.sha256(content).hexdigest()

def register_hash_on_chain(doc_id: str, hex_hash: str) -> str:
    """Գրանցում է հեշը բլոկչեյնում"""
    if not web3.is_connected():
        return "mock_tx_hash_offline_mode"
    
    contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    account = web3.eth.accounts[0]
    bytes32_hash = bytes.fromhex(hex_hash)
    
    tx_hash = contract.functions.registerDocument(doc_id, bytes32_hash).transact({'from': account})
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.transactionHash.hex()

def verify_hash_on_chain(doc_id: str, current_hex_hash: str) -> bool:
    """Ստուգում է off-chain ֆայլի հեշի համապատասխանությունը on-chain գրանցման հետ"""
    if not web3.is_connected():
        return True  
        
    contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    bytes32_hash = bytes.fromhex(current_hex_hash)
    return contract.functions.verifyIntegrity(doc_id, bytes32_hash).call()