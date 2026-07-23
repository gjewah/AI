
# -*- coding: utf-8 -*-
from odoo import fields, models
class VidirESGImport(models.Model):
    _name='vidir.esg.import'; _description='ESG Import (Simplified)'
    name=fields.Char(default='ESG Import')
    total_electricity_kwh=fields.Float()
    total_vehicle_km_diesel=fields.Float()
    total_vehicle_km_petrol=fields.Float()
    total_vehicle_km_ev=fields.Float()
    ev_eff_kwh_100km=fields.Float(default=18.0)
    total_train_pkm=fields.Float()
    total_bus_pkm=fields.Float()
    total_flight_dom_pkm=fields.Float()
    total_flight_sh_pkm=fields.Float()
    total_flight_lh_pkm=fields.Float()
    marine_fuel_ton_hfo=fields.Float()
    marine_fuel_ton_mgo=fields.Float()
    marine_fuel_ton_lng=fields.Float()
    marine_fuel_ton_bio=fields.Float()
    marine_fuel_ton_methanol=fields.Float()
    marine_fuel_ton_ammonia=fields.Float()
