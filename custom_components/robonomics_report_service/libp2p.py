import logging
import typing as tp
import asyncio

from homeassistant.core import HomeAssistant
from pyproxy import Libp2pProxyAPI

from .const import (
    LIBP2P_WS_SERVER,
    LIBP2P_LISTEN_PROTOCOL,
    LIBP2P_SEND_PROTOCOL,
    INTEGRATOR_PEER_ID,
    STORAGE_PINATA_CREDS,
    PROBLEM_SERVICE_ROBONOMICS_ADDRESS,
    CONF_PINATA_PUBLIC,
    CONF_PINATA_SECRET,
)
from .utils import (
    async_save_to_store,
    decrypt_message,
    encrypt_message,
    get_address_for_seed,
)

_LOGGER = logging.getLogger(__name__)


class LibP2P:
    def __init__(self, hass: HomeAssistant, sender_seed: str, email: str):
        self.hass = hass
        self.libp2p_proxy = Libp2pProxyAPI(LIBP2P_WS_SERVER)
        self.sender_seed = sender_seed
        self.sender_address = get_address_for_seed(self.sender_seed)
        self.email = email
        self._pinata_creds_saved = False
        self._listen_protocol = f"{LIBP2P_LISTEN_PROTOCOL}/{self.sender_address}"

    async def get_and_save_pinata_creds(self) -> bool:
        self._pinata_creds_saved = False
        self.libp2p_proxy.subscribe_to_protocol_async(
            self._listen_protocol, self._save_pinata_creds
        )
        await self._send_init_request()
        while not self._pinata_creds_saved:
            await asyncio.sleep(1)
        await self.libp2p_proxy.unsubscribe_from_all_protocols()
        return True

    async def _save_pinata_creds(self, received_data: tp.Union[str, dict]):
        if "public" in received_data and "private" in received_data:
            storage_data = {}
            storage_data[CONF_PINATA_PUBLIC] = self._decrypt_message(
                received_data["public"]
            )
            storage_data[CONF_PINATA_SECRET] = self._decrypt_message(
                received_data["private"]
            )
            await async_save_to_store(
                self.hass,
                STORAGE_PINATA_CREDS,
                storage_data,
            )
            self._pinata_creds_saved = True
            _LOGGER.debug("Got and saved pinata creds")
        else:
            _LOGGER.error(f"Libp2p message in wrong format: {received_data}")

    def _decrypt_message(self, encrypted_data: str) -> str:
        return decrypt_message(
            encrypted_data,
            sender_address=PROBLEM_SERVICE_ROBONOMICS_ADDRESS,
            recipient_seed=self.sender_seed,
        ).decode()

    async def _send_init_request(self) -> None:
        data = self._format_data_for_init_request()
        self.libp2p_proxy.send_msg_to_libp2p(
            data, LIBP2P_SEND_PROTOCOL, server_peer_id=INTEGRATOR_PEER_ID
        )

    def _format_data_for_init_request(self) -> dict:
        encrypted_email = self._encrypt_message(self.email)
        data = {
            "email": encrypted_email,
            "sender_address": self.sender_address,
        }
        return data

    def _encrypt_message(self, data: str) -> str:
        return encrypt_message(
            data,
            sender_seed=self.sender_seed,
            recipient_address=PROBLEM_SERVICE_ROBONOMICS_ADDRESS,
        )
