
# -*- coding: utf-8 -*-
import json
from math import ceil
from odoo import http
from odoo.http import request

def _safe_num(v, d=0.0):
    try:
        x=float(v); return x if x>0 else 0.0
    except: return d

def _get_cfg(name, default):
    val=request.env['ir.config_parameter'].sudo().get_param(name)
    if not val: return default
    try:
        if name.endswith('_json'): return json.loads(val)
        return float(val)
    except: return default

class VidirCO2(http.Controller):
    @http.route('/vidir/co2/compute', type='json', auth='public', csrf=False, methods=['POST'])
    def compute(self, payload=None, **kw):
        payload=payload or {}
        country=payload.get('country') or 'NO'
        user_type=payload.get('user_type') or 'privat'
        grid_map=_get_cfg('vidir_co2.grid_factors_json',{"NO":0.0119})
        trans=_get_cfg('vidir_co2.transport_factors_json',{})
        flt=_get_cfg('vidir_co2.flight_factors_json',{})
        screen_int=_get_cfg('vidir_co2.screening_intensity',6.9)
        grid=payload.get('grid_override')
        try: grid=float(grid)
        except: grid=None
        if not grid or grid<=0: grid=float(grid_map.get(country, grid_map.get('NO',0.0119)))
        def ev_kg(km, eff):
            kwh_km=(_safe_num(eff, trans.get('ev_default_kwh_100km',18.0))/100.0)
            return _safe_num(km)*kwh_km*grid
        def flights_kg(f):
            def pkm(n,d): return _safe_num(n)*(2.0*_safe_num(d))
            return (
                pkm(f.get('dom',{}).get('n'), f.get('dom',{}).get('d'))*flt.get('domestic',0.24587)+
                pkm(f.get('sh',{}).get('n'),  f.get('sh',{}).get('d')) *flt.get('shorthaul',0.18287)+
                pkm(f.get('lh',{}).get('n'),  f.get('lh',{}).get('d')) *flt.get('longhaul',0.20011)
            )
        if user_type=='privat':
            p=payload.get('privat',{})
            el=_safe_num(p.get('el_kwh'))
            car=p.get('car',{})
            car_factor=trans.get('car_diesel',0.16984) if car.get('type')=='diesel' else trans.get('car_petrol',0.1645)
            car_kg=_safe_num(car.get('km'))*car_factor
            ev_kg_val=ev_kg((p.get('ev') or {}).get('km'), (p.get('ev') or {}).get('eff_kwh_100km'))
            train=_safe_num(p.get('train_pkm'))*trans.get('train',0.03546)
            bus=_safe_num(p.get('bus_pkm'))*trans.get('bus',0.10846)
            fly=flights_kg(p.get('flights',{}))
            total_kg=el*grid+car_kg+ev_kg_val+train+bus+fly
            total_t=total_kg/1000.0; credits=ceil(total_t)
            res={"country":country,"grid_factor":grid,"total_t":total_t,"credits":credits}
        else:
            b=payload.get('bedrift',{})
            intensity=_safe_num(b.get('screen_intensity'),screen_int)
            revenue=_safe_num(b.get('revenue_mnok'))
            screening=intensity*revenue
            el=_safe_num(b.get('el_kwh'))
            diesel=_safe_num(b.get('diesel_km'))*trans.get('car_diesel',0.16984)
            petrol=_safe_num(b.get('petrol_km'))*trans.get('car_petrol',0.1645)
            evk=ev_kg(b.get('ev_km'), b.get('ev_eff_kwh_100km'))
            train=_safe_num(b.get('train_pkm'))*trans.get('train',0.03546)
            bus=_safe_num(b.get('bus_pkm'))*trans.get('bus',0.10846)
            fly=flights_kg(b.get('flights',{}))
            activity_kg=el*grid+diesel+petrol+evk+train+bus+fly
            activity_t=activity_kg/1000.0
            total_t=screening+activity_t; credits=ceil(total_t)
            res={"country":country,"grid_factor":grid,"screening_t":screening,"activity_t":activity_t,"total_t":total_t,"credits":credits}
        request.env['vidir.co2.request'].sudo().create({'user_type':user_type,'country':country,'input_json':payload,'result_json':res,'total_t':res.get('total_t') or res.get('activity_t') or 0.0,'credits':res.get('credits') or 0})
        return res
