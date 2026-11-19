"""La card è JavaScript, ma un controllo statico basta a prendere l'errore più stupido: una vista dichiarata e senza metodo."""
import pathlib
import re

JS = (pathlib.Path(__file__).parents[1] / "custom_components/didup/frontend/didup-card.js").read_text(encoding="utf-8")


def test_ogni_vista_ha_il_suo_metodo():
    viste = re.search(r"const VISTE = \[(.*?)\];", JS).group(1)
    nomi = re.findall(r'"(\w+)"', viste)
    assert len(nomi) >= 8
    mancanti = [v for v in nomi if not re.search(rf"^  _v_{v}\(t\) \{{", JS, re.M)]
    assert not mancanti, f"viste senza metodo _v_<nome>: {mancanti}"


def test_la_versione_della_card_segue_il_manifest():
    import json
    manifest = json.loads((pathlib.Path(__file__).parents[1] / "custom_components/didup/manifest.json").read_text())
    assert f'DIDUP_CARD_VERSION = "{manifest["version"]}"' in JS
