from django.db import models
from django.contrib.auth.models import User
from django_mongodb_backend.fields import ObjectIdAutoField
from apps.zonas.models import Zona


class ScriptGEE(models.Model):
    id                    = ObjectIdAutoField(primary_key=True)
    nombre                = models.CharField(max_length=200)
    fuente                = models.CharField(max_length=10)  # era5/modis
    archivo_csv           = models.CharField(max_length=200)
    columnas_detectadas   = models.JSONField(default=list)
    columnas_extra        = models.JSONField(default=list)
    registros_importados  = models.IntegerField(default=0)
    registros_rechazados  = models.IntegerField(default=0)
    subido_por            = models.ForeignKey(User, on_delete=models.PROTECT)
    subido_en             = models.DateTimeField(auto_now_add=True)
    estado                = models.CharField(max_length=20, default='activo')

    class Meta:
        db_table = 'scripts_gee'

    def __str__(self):
        return self.nombre


class Medicion(models.Model):
    id               = ObjectIdAutoField(primary_key=True)
    zona             = models.ForeignKey(Zona, on_delete=models.PROTECT)
    zona_nombre      = models.CharField(max_length=100)
    fecha            = models.DateField()
    fuente           = models.CharField(max_length=10)  # era5/modis

    # ERA5
    temperatura_c     = models.FloatField(null=True, blank=True)
    temperatura_min_c = models.FloatField(null=True, blank=True)
    temperatura_max_c = models.FloatField(null=True, blank=True)
    precipitacion_mm  = models.FloatField(null=True, blank=True)
    dewpoint_c        = models.FloatField(null=True, blank=True)
    viento_u          = models.FloatField(null=True, blank=True)
    viento_v          = models.FloatField(null=True, blank=True)
    humedad_suelo     = models.FloatField(null=True, blank=True)
    cobertura_nieve   = models.FloatField(null=True, blank=True)
    radiacion_solar   = models.FloatField(null=True, blank=True)

    # MODIS
    ndvi              = models.FloatField(null=True, blank=True)
    evi               = models.FloatField(null=True, blank=True)
    quality_modis     = models.IntegerField(null=True, blank=True)

    # Control
    extra             = models.JSONField(default=dict)
    validado          = models.BooleanField(default=True)
    script            = models.ForeignKey(
        ScriptGEE, on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        db_table = 'mediciones'

    def __str__(self):
        return f"{self.zona_nombre} - {self.fecha} - {self.fuente}"