"""Constants for the Ht HA integration."""

from typing import Final

# Domain
DOMAIN: Final = "htha"

# Configuration keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_TIMEOUT: Final = "timeout"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_WRITE_ENABLED: Final = "write_enabled"
CONF_SELECTED_PARAMS: Final = "selected_params"

# Default values
DEFAULT_PORT: Final = 9999
DEFAULT_TIMEOUT: Final = 10
DEFAULT_SCAN_INTERVAL: Final = 30

# Parameter categories for UI organization
PARAM_CATEGORIES: Final[dict[str, list[str]]] = {
    "temperatures": [
        "Temp. Aussen",
        "Temp. Aussen verzoegert",
        "Temp. Brauchwasser",
        "Temp. Vorlauf",
        "Temp. Ruecklauf",
        "Temp. EQ_Eintritt",
        "Temp. EQ_Austritt",
        "Temp. Sauggas",
        "Temp. Frischwasser_Istwert",
        "Temp. Verdampfung",
        "Temp. Kondensation",
        "Temp. Heissgas",
    ],
    "pressures": [
        "Niederdruck (bar)",
        "Hochdruck (bar)",
    ],
    "status": [
        "Heizkreispumpe",
        "EQ Pumpe (Ventilator)",
        "Warmwasservorrang",
        "Zirkulationspumpe WW",
        "Verdichter",
        "Stoerung",
        "Hauptschalter",
        "FWS Stroemungsschalter",
    ],
    "setpoints": [
        "HKR Soll_Raum",
        "HKR RLT Soll_oHG (Heizkurve)",
        "HKR RLT Soll_0 (Heizkurve)",
        "HKR RLT Soll_uHG (Heizkurve)",
        "WW Normaltemp.",
        "WW Minimaltemp.",
    ],
    "operating_mode": [
        "Betriebsart",
    ],
    "statistics": [
        "BSZ Verdichter Schaltungen",
        "BSZ HKP Betriebsstunden",
        "BSZ EQ Betriebsstunden",
        "BSZ WWV Betriebsstunden",
    ],
}

# Default curated parameters to expose
DEFAULT_PARAMS: Final[list[str]] = [
    # Temperatures (working)
    "Temp. Aussen",
    "Temp. Aussen verzoegert",
    "Temp. Brauchwasser",
    "Temp. Vorlauf",
    "Temp. Ruecklauf",
    "Temp. EQ_Eintritt",
    "Temp. EQ_Austritt",
    "Temp. Sauggas",
    # Note: Temp. Frischwasser_Istwert, Temp. Verdampfung, Temp. Kondensation,
    # Temp. Heissgas may not be available on all heat pump models
    # Status
    "Heizkreispumpe",
    "EQ Pumpe (Ventilator)",
    "Zirkulationspumpe WW",
    "Verdichter",
    "Stoerung",
    "Warmwasservorrang",
    "Hauptschalter",
    "FWS Stroemungsschalter",
    # Setpoints
    "HKR Soll_Raum",
    "WW Normaltemp.",
    "WW Minimaltemp.",
    "HKR RLT Soll_oHG (Heizkurve)",
    "HKR RLT Soll_0 (Heizkurve)",
    "HKR RLT Soll_uHG (Heizkurve)",
    # Operating mode
    "Betriebsart",
    # Statistics
    "BSZ Verdichter Schaltungen",
    "BSZ HKP Betriebsstunden",
    "BSZ EQ Betriebsstunden",
    "BSZ WWV Betriebsstunden",
]

# Operating mode mapping for select entity
# Keys must match [a-z0-9-_]+ pattern for translation validation
OPERATING_MODES: Final[dict[int, str]] = {
    0: "off",
    1: "heating",
    2: "cooling",
    3: "hot_water",
    4: "heating_cooling",
    5: "auto",
    6: "emergency",
    7: "standby",
}

# Parameter metadata for entity creation
# Maps parameter names to their entity configuration
PARAM_SENSOR_METADATA: Final[dict[str, dict]] = {
    # Temperatures - in °C
    "Temp. Aussen": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Aussen verzoegert": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Brauchwasser": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:water-thermometer",
    },
    "Temp. Vorlauf": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer-lines",
    },
    "Temp. Ruecklauf": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer-lines",
    },
    "Temp. EQ_Eintritt": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. EQ_Austritt": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Sauggas": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Frischwasser_Istwert": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:water-thermometer",
    },
    "Temp. Verdampfung": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Kondensation": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "Temp. Heissgas": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer-alert",
    },
    # Pressures - in bar
    "Niederdruck (bar)": {
        "device_class": "pressure",
        "unit": "bar",
        "state_class": "measurement",
        "icon": "mdi:gauge",
    },
    "Hochdruck (bar)": {
        "device_class": "pressure",
        "unit": "bar",
        "state_class": "measurement",
        "icon": "mdi:gauge",
    },
    # HKR_Sollwert
    "HKR_Sollwert": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    # Statistics - counters
    "BSZ Verdichter Schaltungen": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    "BSZ HKP Betriebsstunden": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ EQ Betriebsstunden": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ WWV Betriebsstunden": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ ZIPWW Betriebsstunden": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ Verdichter Betriebsst. WW": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ Verdichter Betriebsst. HKR": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ Verdichter Betriebsst. ges": {
        "device_class": None,
        "unit": "h",
        "state_class": "total_increasing",
        "icon": "mdi:clock-outline",
    },
    "BSZ Verdichter akt. Laufzeit": {
        "device_class": None,
        "unit": "min",
        "state_class": "measurement",
        "icon": "mdi:timer-outline",
    },
    "BSZ Verdichter Schaltung WW": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    "BSZ HKP Schaltung": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    "BSZ EQ Schaltungen": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    "BSZ WWV Schaltungen": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    "BSZ ZIPWW Schaltungen": {
        "device_class": None,
        "unit": None,
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    # Other numeric parameters
    "Verdichter_Status": {
        "device_class": None,
        "unit": None,
        "state_class": "measurement",
        "icon": "mdi:information-outline",
    },
    "Verdichter laeuft seit": {
        "device_class": None,
        "unit": "s",
        "state_class": "measurement",
        "icon": "mdi:timer-outline",
    },
    "Verdichter Einschaltverz.(sec)": {
        "device_class": None,
        "unit": "s",
        "state_class": "measurement",
        "icon": "mdi:timer-sand",
    },
    "Verdichteranforderung": {
        "device_class": None,
        "unit": None,
        "state_class": "measurement",
        "icon": "mdi:numeric",
    },
    "Frischwasserpumpe": {
        "device_class": None,
        "unit": "%",
        "state_class": "measurement",
        "icon": "mdi:water-pump",
    },
    "HKR Aufheiztemp. (K)": {
        "device_class": "temperature",
        "unit": "K",
        "state_class": "measurement",
        "icon": "mdi:thermometer-plus",
    },
    "HKR Absenktemp. (K)": {
        "device_class": "temperature",
        "unit": "K",
        "state_class": "measurement",
        "icon": "mdi:thermometer-minus",
    },
    "HKR Heizgrenze": {
        "device_class": None,
        "unit": None,
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "HKR RLT Soll_oHG (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "HKR RLT Soll_0 (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "HKR RLT Soll_uHG (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "WW Hysterese Normaltemp.": {
        "device_class": "temperature",
        "unit": "K",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "WW Hysterese Minimaltemp.": {
        "device_class": "temperature",
        "unit": "K",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
}

# Binary sensor metadata
PARAM_BINARY_SENSOR_METADATA: Final[dict[str, dict]] = {
    "Stoerung": {
        "device_class": "problem",
        "icon_on": "mdi:alert",
        "icon_off": "mdi:check-circle",
    },
    "Heizkreispumpe": {
        "device_class": "running",
        "icon_on": "mdi:pump",
        "icon_off": "mdi:pump",
    },
    "EQ Pumpe (Ventilator)": {
        "device_class": "running",
        "icon_on": "mdi:fan",
        "icon_off": "mdi:fan-off",
    },
    "Warmwasservorrang": {
        "device_class": "running",
        "icon_on": "mdi:water-boiler",
        "icon_off": "mdi:water-boiler",
    },
    "Zirkulationspumpe WW": {
        "device_class": "running",
        "icon_on": "mdi:water-pump",
        "icon_off": "mdi:water-pump-off",
    },
    "Verdichter": {
        "device_class": "running",
        "icon_on": "mdi:engine",
        "icon_off": "mdi:engine-outline",
    },
    "Hauptschalter": {
        "device_class": "power",
        "icon_on": "mdi:power-plug",
        "icon_off": "mdi:power-plug-off",
    },
    "FWS Stroemungsschalter": {
        "device_class": "running",
        "icon_on": "mdi:water-check",
        "icon_off": "mdi:water-remove",
    },
}

# Number entity metadata (for setpoints)
PARAM_NUMBER_METADATA: Final[dict[str, dict]] = {
    "HKR Soll_Raum": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 0.5,
    },
    "WW Normaltemp.": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:water-thermometer",
        "mode": "box",
        "step": 1,
    },
    "WW Minimaltemp.": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:water-thermometer",
        "mode": "box",
        "step": 1,
    },
    "HKR RLT Soll_oHG (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 0.5,
    },
    "HKR RLT Soll_0 (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 0.5,
    },
    "HKR RLT Soll_uHG (Heizkurve)": {
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 0.5,
    },
    "HKR Aufheiztemp. (K)": {
        "device_class": "temperature",
        "unit": "K",
        "icon": "mdi:thermometer-plus",
        "mode": "box",
        "step": 1,
    },
    "HKR Absenktemp. (K)": {
        "device_class": "temperature",
        "unit": "K",
        "icon": "mdi:thermometer-minus",
        "mode": "box",
        "step": 1,
    },
    "HKR Heizgrenze": {
        "device_class": None,
        "unit": None,
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 1,
    },
    "WW Hysterese Normaltemp.": {
        "device_class": "temperature",
        "unit": "K",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 1,
    },
    "WW Hysterese Minimaltemp.": {
        "device_class": "temperature",
        "unit": "K",
        "icon": "mdi:thermometer",
        "mode": "box",
        "step": 1,
    },
}

# Select entity metadata (for operating mode)
PARAM_SELECT_METADATA: Final[dict[str, dict]] = {
    "Betriebsart": {
        "icon": "mdi:home-automation",
        "options": list(OPERATING_MODES.values()),
    },
}

# Translation key mapping for entity names
# Maps German parameter names to valid translation keys [a-z0-9_]+
PARAM_TRANSLATION_KEYS: Final[dict[str, str]] = {
    # Temperatures
    "Temp. Aussen": "temp_aussen",
    "Temp. Aussen verzoegert": "temp_aussen_verzoegert",
    "Temp. Brauchwasser": "temp_brauchwasser",
    "Temp. Vorlauf": "temp_vorlauf",
    "Temp. Ruecklauf": "temp_ruecklauf",
    "Temp. EQ_Eintritt": "temp_eq_eintritt",
    "Temp. EQ_Austritt": "temp_eq_austritt",
    "Temp. Sauggas": "temp_sauggas",
    "Temp. Frischwasser_Istwert": "temp_frischwasser_istwert",
    "Temp. Verdampfung": "temp_verdampfung",
    "Temp. Kondensation": "temp_kondensation",
    "Temp. Heissgas": "temp_heissgas",
    # Pressures
    "Niederdruck (bar)": "niederdruck",
    "Hochdruck (bar)": "hochdruck",
    # Status (binary sensors)
    "Stoerung": "stoerung",
    "Heizkreispumpe": "heizkreispumpe",
    "EQ Pumpe (Ventilator)": "eq_pumpe_ventilator",
    "Warmwasservorrang": "warmwasservorrang",
    "Zirkulationspumpe WW": "zirkulationspumpe_ww",
    "Verdichter": "verdichter",
    "Hauptschalter": "hauptschalter",
    "FWS Stroemungsschalter": "fws_stroemungsschalter",
    # Setpoints (number entities)
    "HKR Soll_Raum": "hkr_soll_raum",
    "WW Normaltemp.": "ww_normaltemp",
    "WW Minimaltemp.": "ww_minimaltemp",
    "HKR RLT Soll_oHG (Heizkurve)": "hkr_rlt_soll_ohg",
    "HKR RLT Soll_0 (Heizkurve)": "hkr_rlt_soll_0",
    "HKR RLT Soll_uHG (Heizkurve)": "hkr_rlt_soll_uhg",
    "HKR Aufheiztemp. (K)": "hkr_aufheiztemp",
    "HKR Absenktemp. (K)": "hkr_absenktemp",
    "HKR Heizgrenze": "hkr_heizgrenze",
    "WW Hysterese Normaltemp.": "ww_hysterese_normaltemp",
    "WW Hysterese Minimaltemp.": "ww_hysterese_minimaltemp",
    # Operating mode
    "Betriebsart": "betriebsart",
    # Statistics
    "BSZ Verdichter Schaltungen": "bsz_verdichter_schaltungen",
    "BSZ HKP Betriebsstunden": "bsz_hkp_betriebsstunden",
    "BSZ EQ Betriebsstunden": "bsz_eq_betriebsstunden",
    "BSZ WWV Betriebsstunden": "bsz_wwv_betriebsstunden",
    # Other
    "HKR_Sollwert": "hkr_sollwert",
    "BSZ ZIPWW Betriebsstunden": "bsz_zipww_betriebsstunden",
    "BSZ Verdichter Betriebsst. WW": "bsz_verdichter_betriebsst_ww",
    "BSZ Verdichter Betriebsst. HKR": "bsz_verdichter_betriebsst_hkr",
    "BSZ Verdichter Betriebsst. ges": "bsz_verdichter_betriebsst_ges",
    "BSZ Verdichter akt. Laufzeit": "bsz_verdichter_akt_laufzeit",
    "BSZ Verdichter Schaltung WW": "bsz_verdichter_schaltung_ww",
    "BSZ HKP Schaltung": "bsz_hkp_schaltung",
    "BSZ EQ Schaltungen": "bsz_eq_schaltungen",
    "BSZ WWV Schaltungen": "bsz_wwv_schaltungen",
    "BSZ ZIPWW Schaltungen": "bsz_zipww_schaltungen",
    "Verdichter_Status": "verdichter_status",
    "Verdichter laeuft seit": "verdichter_laeft_seit",
    "Verdichter Einschaltverz.(sec)": "verdichter_einschaltverz",
    "Verdichteranforderung": "verdichteranforderung",
    "Frischwasserpumpe": "frischwasserpumpe",
}
