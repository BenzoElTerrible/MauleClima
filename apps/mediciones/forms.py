from django import forms
from apps.mediciones.models import Medicion

FUENTE_CHOICES = [('ERA5', 'ERA5'), ('MODIS', 'MODIS')]


class MedicionForm(forms.ModelForm):
    fuente = forms.ChoiceField(choices=FUENTE_CHOICES)

    class Meta:
        model = Medicion
        fields = [
            'zona', 'fecha', 'fuente',
            'temperatura_c', 'temperatura_min_c', 'temperatura_max_c',
            'precipitacion_mm', 'dewpoint_c', 'viento_u', 'viento_v',
            'humedad_suelo', 'cobertura_nieve', 'radiacion_solar',
            'ndvi', 'evi', 'quality_modis',
            'extra', 'validado',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre == 'validado':
                continue
            campo.widget.attrs.setdefault('class', 'form-control')
            if isinstance(campo.widget, forms.NumberInput):
                campo.widget.attrs.setdefault('step', 'any')