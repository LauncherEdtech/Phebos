import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pixzap.bot import Bot  # noqa: E402
from pixzap.matching import Reconciler  # noqa: E402
from pixzap.psp.fake import FakePsp  # noqa: E402
from pixzap.storage import Storage  # noqa: E402
from pixzap.whatsapp.fake import FakeWhatsApp  # noqa: E402

SELLER = "5511999998888"


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


@pytest.fixture
def psp():
    return FakePsp(webhook_token="segredo")


@pytest.fixture
def wa():
    return FakeWhatsApp()


@pytest.fixture
def bot(storage, psp):
    return Bot(storage, psp, seller_numbers=[SELLER])


@pytest.fixture
def reconciler(storage):
    return Reconciler(storage)
