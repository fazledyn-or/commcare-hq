from crispy_forms.bootstrap import AccordionGroup
from crispy_forms.layout import MultiField, TEMPLATE_PACK, Field
from crispy_forms.utils import render_field
from django.template.loader import render_to_string


class BootstrapMultiField(MultiField):
    template = "hqwebapp/crispy/layout/multifield.html"
    field_template = "hqwebapp/crispy/field/multifield.html"

    def render(self, form, form_style, context, template_pack=TEMPLATE_PACK):
        fields_output = u''
        for field in self.fields:
            fields_output += render_field(
                field, form, form_style, context,
                self.field_template, self.label_class, layout_object=self,
                template_pack=template_pack
            )

        errors = self._get_errors(form, self.fields)
        if len(errors) > 0:
            self.css_class += " error"

        context.update({
            'multifield': self,
            'fields_output': fields_output,
            'error_list': errors,
        })
        return render_to_string(self.template, context)

    def _get_errors(self, form, fields):
        errors = []
        for field in fields:
            if isinstance(field, Field) or issubclass(field.__class__, Field):
                fname = field.fields[0]
                error = form[fname].errors
                if error:
                    errors.append(error)
            else:
                try:
                    errors.extend(self._get_errors(form, field.fields))
                except AttributeError:
                    pass
        return errors


class FieldsetAccordionGroup(AccordionGroup):
    template = "hqwebapp/crispy/layout/fieldset_accordion_group.html"


class HiddenFieldWithErrors(Field):
    template = "hqwebapp/crispy/field/hidden_with_errors.html"
