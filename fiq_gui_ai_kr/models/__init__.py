# Odoo laster modellene HERFRA — importene ser ubrukte ut for en linter,
# men uten dem finnes ikke modellene i registeret og modulen er tom.
# 🛑 ALDRI fjern en import her fordi et verktoy melder F401.
# ruff: noqa: F401
from . import (
    fiq_ai_godkjenning,  # ett sted å svare — «Alltid» stopper gjentakelsen
    fiq_ai_konklusjon,  # det Gjermund skal kunne lese OG stoppe
    fiq_ai_melding,
    fiq_ai_okt,
    fiq_ai_regel,  # reglene i klartekst - Gjermund har aldri sett dem
    fiq_ai_spor,  # sporet er den varige enheten
    fiq_ai_stadie,  # fem stadier - native project.task.type
    fiq_gui_ai_kr_data,
    fiq_gui_comm_kanal,  # AI-meldinger som kanal i Meldingssenteret
)
