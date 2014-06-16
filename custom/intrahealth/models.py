import fluff
from couchforms.models import XFormInstance
from fluff.filters import ORFilter
from corehq.fluff.calculators.xform import FormPropertyFilter
from custom.intrahealth import INTRAHEALTH_DOMAINS, report_calcs, OPERATEUR_XMLNSES, get_real_date, \
    get_location_id, get_location_id_by_type, COMMANDE_XMLNSES, get_products


def _get_all_forms():
    form_filters = []
    for xmlns in OPERATEUR_XMLNSES:
        form_filters.append(FormPropertyFilter(xmlns=xmlns))
    return form_filters


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)


class CouvertureFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])

    domains = INTRAHEALTH_DOMAINS
    group_by = ('domain', fluff.AttributeGetter('location_id', get_location_id))
    save_direct_to_sql = True

    location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    real_date_repeat = flat_field(get_real_date)
    registered = report_calcs.PPSRegistered()
    planned = report_calcs.PPSPlaned()

class TauxDeSatisfactionFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ORFilter([
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[0]),
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[1])
        ])

    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'productName')),)
    save_direct_to_sql = True

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    commandes = report_calcs.Commandes()
    recus = report_calcs.Recus()

class FicheFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])
    domains = INTRAHEALTH_DOMAINS
    save_direct_to_sql = True
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),)

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    PPS_name = flat_field(lambda f: f.form['PPS_name'])
    location_id = flat_field(get_location_id)
    actual_consumption = report_calcs.PPSConsumption()
    billed_consumption = report_calcs.PPSConsumption(field='billed_consumption')

class RecapPassageFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])

    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),)
    save_direct_to_sql = True

    location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    real_date_repeat = flat_field(get_real_date)
    PPS_name = flat_field(lambda f: f.form['PPS_name'])

    product = report_calcs.RecapPassage()

class ConsommationFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])
    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),)
    save_direct_to_sql = True

    PPS_name = flat_field(lambda f: f.form['PPS_name'])
    district_name = flat_field(lambda f: f.form['district_name'])
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))

    consumption = report_calcs.PPSConsumption()

class TauxConsommationFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])
    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),)
    save_direct_to_sql = True

    PPS_name = flat_field(lambda f: f.form['PPS_name'])
    district_name = flat_field(lambda f: f.form['district_name'])
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))

    consumption = report_calcs.PPSConsumption()
    stock = report_calcs.PPSConsumption('old_stock_total')

class NombreFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])
    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),)
    save_direct_to_sql = True

    PPS_name = flat_field(lambda f: f.form['PPS_name'])
    district_name = flat_field(lambda f: f.form['district_name'])
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))

    quantity = report_calcs.PPSConsumption('display_total_stock')
    cmm = report_calcs.PPSConsumption('default_consumption')

CouvertureFluffPillow = CouvertureFluff.pillow()
FicheFluffPillow = FicheFluff.pillow()
RecapPassagePillow = RecapPassageFluff.pillow()
TauxDeSatisfactionFluffPillow = TauxDeSatisfactionFluff.pillow()
ConsommationFluffPillow = ConsommationFluff.pillow()
TauxConsommationFluffPillow = TauxConsommationFluff.pillow()
NombreFluffPillow = NombreFluff.pillow()
