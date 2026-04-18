from backend.scripts.scenarios.busan_strike import BUSAN_STRIKE
from backend.scripts.scenarios.cbam_tariff import CBAM_TARIFF
from backend.scripts.scenarios.luxshare_fire import LUXSHARE_FIRE
from backend.scripts.scenarios.redsea_advisory import REDSEA_ADVISORY
from backend.scripts.scenarios.typhoon_kaia import TYPHOON_KAIA

SCENARIOS: dict[str, object] = {
    "typhoon_kaia": TYPHOON_KAIA,
    "busan_strike": BUSAN_STRIKE,
    "cbam_tariff": CBAM_TARIFF,
    "luxshare_fire": LUXSHARE_FIRE,
    "redsea_advisory": REDSEA_ADVISORY,
}
