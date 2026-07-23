
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import io, json
try:
    import openpyxl
except Exception:
    openpyxl=None

class VidirExport(http.Controller):
    def _get_factor(self, profile, code, default=0.0):
        if not profile:
            return default
        rec = request.env['vidir.industry.factor.set'].sudo().search([('profile_id','=',profile.id),('code','=',code)], limit=1)
        return rec.value if rec else default

    def _map_code(self, company, category, target):
        rec = request.env['vidir.export.map'].sudo().search([('company_id','=',company.id),('category','=','%s'%category),('target','=',target)], limit=1)
        return rec.account_code if rec else category

    @http.route(['/dpp/<string:uuid>/export/xlsx'], type='http', auth='public')
    def export_esg(self, uuid, erp=None, **kw):
        if not openpyxl:
            return request.make_response('Missing openpyxl (optional). Install to enable Excel export.', [('Content-Type','text/plain; charset=utf-8')])
        dpp=request.env['vidir.dpp.passport'].sudo().search([('uuid','=',uuid)], limit=1)
        if not dpp:
            return request.not_found()
        esg=request.env['vidir.esg.import'].sudo().search([], order='id desc', limit=1)
        ICP=request.env['ir.config_parameter'].sudo()
        try:
            grid_map=json.loads(ICP.get_param('vidir_co2.grid_factors_json') or '{}')
        except Exception:
            grid_map={}
        try:
            trans=json.loads(ICP.get_param('vidir_co2.transport_factors_json') or '{}')
        except Exception:
            trans={}
        try:
            flight=json.loads(ICP.get_param('vidir_co2.flight_factors_json') or '{}')
        except Exception:
            flight={}
        country=(dpp.country_of_origin or 'NO').upper()
        profile = dpp.industry_profile_id if hasattr(dpp, 'industry_profile_id') else False
        grid=self._get_factor(profile, f'grid_{country}', float(grid_map.get(country, grid_map.get('NO', 0.0119))))
        ev_eff_default=float(trans.get('ev_default_kwh_100km', 18.0))
        wb=openpyxl.Workbook(); ws=wb.active; ws.title='ESG'
        header=['Period','Country','Account/Code' if erp else 'Category','Unit','Amount','CO2e_kg','Notes']
        ws.append(header)
        def add(period,country,cat,unit,amount,co2e_kg,notes=''):
            out_cat=self._map_code(dpp.company_id, cat, erp) if erp else cat
            ws.append([period,country,out_cat,unit,amount,co2e_kg,notes])
        period='CY'; ctry=country
        if esg:
            el=esg.total_electricity_kwh or 0.0
            add(period,ctry,'electricity_kwh','kWh', el, round(el*grid, 3), f'DPP {dpp.uuid}')
            dk=esg.total_vehicle_km_diesel or 0.0
            pk=esg.total_vehicle_km_petrol or 0.0
            evk=esg.total_vehicle_km_ev or 0.0
            add(period,ctry,'vehicle_km_diesel','km', dk, round(dk*self._get_factor(profile,'car_diesel', 0.16984), 3))
            add(period,ctry,'vehicle_km_petrol','km', pk, round(pk*self._get_factor(profile,'car_petrol', 0.1645), 3))
            ev_eff=getattr(esg,'ev_eff_kwh_100km', None) or ev_eff_default
            add(period,ctry,'vehicle_km_ev','km', evk, round(evk*(float(ev_eff)/100.0)*grid, 3))
            tp=esg.total_train_pkm or 0.0
            bp=esg.total_bus_pkm or 0.0
            add(period,ctry,'train_pkm','pkm', tp, round(tp*self._get_factor(profile,'train', 0.03546), 3))
            add(period,ctry,'bus_pkm','pkm', bp, round(bp*self._get_factor(profile,'bus', 0.10846), 3))
            fd=esg.total_flight_dom_pkm or 0.0
            fs=esg.total_flight_sh_pkm or 0.0
            fl=esg.total_flight_lh_pkm or 0.0
            add(period,ctry,'flight_dom_pkm','pkm', fd, round(fd*self._get_factor(profile,'flight_domestic', 0.24587), 3))
            add(period,ctry,'flight_sh_pkm','pkm',  fs, round(fs*self._get_factor(profile,'flight_shorthaul', 0.18287), 3))
            add(period,ctry,'flight_lh_pkm','pkm',  fl, round(fl*self._get_factor(profile,'flight_longhaul', 0.20011), 3))
            for code in ['hfo','mgo','lng','bio','methanol','ammonia']:
                amount = getattr(esg, f'marine_fuel_ton_{code}', 0.0) or 0.0
                if amount:
                    factor = self._get_factor(profile, f'marine_fuel_ton_{code}', 0.0)
                    add(period, ctry, f'marine_fuel_ton_{code}', 'ton', amount, round(amount*factor, 3))
            if not any((getattr(esg, f'marine_fuel_ton_{c}', 0.0) or 0.0) > 0 for c in ['hfo','mgo','lng','bio','methanol','ammonia']):
                if getattr(dpp, 'default_marine_fuel_type', False) and (getattr(dpp, 'default_marine_fuel_ton', 0.0) or 0.0) > 0:
                    code=dpp.default_marine_fuel_type; amount=dpp.default_marine_fuel_ton
                    factor=self._get_factor(profile, f'marine_fuel_ton_{code}', 0.0)
                    if factor>0:
                        add(period, ctry, f'marine_fuel_ton_{code}', 'ton', amount, round(amount*factor, 3), 'DPP default')
        bio=io.BytesIO(); wb.save(bio); bio.seek(0)
        return request.make_response(bio.read(), [
            ('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename="ESG_{dpp.uuid}.xlsx"')
        ])
