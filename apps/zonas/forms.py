from django import forms
from apps.zonas.models import Zona


class ZonaForm(forms.ModelForm):
    class Meta:
        model = Zona
        fields = ['nombre', 'codigo_ine', 'provincia', 'lat', 'lon', 'cuenca']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'form-control')
            if isinstance(campo.widget, forms.NumberInput):
                campo.widget.attrs.setdefault('step', 'any')