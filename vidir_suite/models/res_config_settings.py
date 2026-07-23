
# -*- coding: utf-8 -*-
import json
from odoo import fields, models
DEFAULT_GRID={"NO":0.0119}
DEFAULT_TRANSPORT={"car_petrol":0.1645,"car_diesel":0.16984,"train":0.03546,"bus":0.10846,"ev_default_kwh_100km":18.0}
DEFAULT_FLIGHT={"domestic":0.24587,"shorthaul":0.18287,"longhaul":0.20011}
class ResConfigSettings(models.TransientModel):
    _inherit='res.config.settings'
    co2_grid_factors=fields.Text(string='Strømfaktorer (kg/kWh)', default=lambda s: json.dumps(DEFAULT_GRID), config_parameter='vidir_co2.grid_factors_json')
    co2_transport_factors=fields.Text(string='Transportfaktorer (DEFRA)', default=lambda s: json.dumps(DEFAULT_TRANSPORT), config_parameter='vidir_co2.transport_factors_json')
    co2_flight_factors=fields.Text(string='Flyfaktorer (DEFRA, RF)', default=lambda s: json.dumps(DEFAULT_FLIGHT), config_parameter='vidir_co2.flight_factors_json')
    co2_screening_intensity=fields.Float(string='Screening-intensitet (t/MNOK)', default=6.9, config_parameter='vidir_co2.screening_intensity')
