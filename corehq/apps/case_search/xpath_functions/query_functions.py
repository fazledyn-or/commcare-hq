from django.utils.translation import gettext as _

from eulxml.xpath import serialize
from eulxml.xpath.ast import Step
from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    case_property_geo_distance,
    case_property_query,
)

from .utils import confirm_args_count


def not_(node, context):
    from corehq.apps.case_search.filter_dsl import build_filter_from_ast
    confirm_args_count(node, 1)
    return filters.NOT(build_filter_from_ast(node.args[0], context))


def selected_any(node, context):
    return _selected_query(node, context, operator='or')


def selected_all(node, context):
    return _selected_query(node, context, operator='and')


def _selected_query(node, context, operator):
    confirm_args_count(node, 2)

    property_name, search_values = node.args
    property_name = _property_name_to_string(property_name, node)
    return case_property_query(property_name, search_values, fuzzy=context.fuzzy, multivalue_mode=operator)


# TODO validate distance format
def proximity(node, context):
    confirm_args_count(node, 3)
    property_name, coords, distance = node.args
    property_name = _property_name_to_string(property_name, node)

    try:
        geo_point = GeoPoint.from_string(coords, flexible=True)
    except BadValueError as e:
        raise XPathFunctionException(
            _(f"The second argument to '{node.name}' must be valid coordinates"),
            serialize(node)
        ) from e

    return case_property_geo_distance(property_name, geo_point, distance)


def _property_name_to_string(value, node):
    if isinstance(value, Step):
        return serialize(value)
    if isinstance(value, str):
        return value
    raise XPathFunctionException(
        _(f"The first argument to '{node.name}' must be a valid case property name"),
        serialize(node)
    )
