from __future__ import absolute_import

from django.test import SimpleTestCase

from dimagi.ext.couchdbkit import (
    DocumentSchema,
    SchemaDictProperty,
    SchemaProperty,
    StringProperty,
)


class Ham(DocumentSchema):
    eggs = StringProperty()

    def __eq__(self, other):
        return self.doc_type == other.doc_type and self.eggs == other.eggs


class Spam(DocumentSchema):
    ham = Ham(required=False)
    ham_prop = SchemaProperty(Ham, required=False)
    ham_dict_prop = SchemaDictProperty(Ham, required=False)


class SchemaTests(SimpleTestCase):
    """
    Demonstrates the difference between DocumentSchema, SchemaProperty
    and SchemaDictProperty
    """

    def test_schemas(self):
        spam = dict(Spam.wrap({}))
        self.assertSetEqual(set(spam.keys()), {'doc_type', 'ham_dict_prop', 'ham_prop'})  # ham is not in spam
        self.assertEqual(spam['ham_prop'], Ham(doc_type='Ham', eggs=None))
        self.assertDictEqual(spam['ham_dict_prop'], {})
