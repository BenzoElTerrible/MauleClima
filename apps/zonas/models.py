from django.db import models
from django_mongodb_backend.fields import ObjectIdAutoField


class Provincia(models.Model):
    id       = ObjectIdAutoField(primary_key=True)
    nombre   = models.CharField(max_length=100)
    region   = models.CharField(max_length=100, default='Del Maule') # valor fijo por defecto para cada provincea

    class Meta:
        db_table = 'provincias' # nombre de la coleccion mongodb relacionada a provincias

    def __str__(self):
        return self.nombre


class Zona(models.Model):
    id        = ObjectIdAutoField(primary_key=True)
    nombre    = models.CharField(max_length=100)
    codigo_ine  = models.CharField(max_length=10, blank=True, default='')
    provincia = models.ForeignKey(
        Provincia, on_delete=models.PROTECT, related_name='zonas' #provincia.zonas.alll()
    )
    lat       = models.FloatField()
    lon       = models.FloatField()
    cuenca    = models.CharField(max_length=100, blank=True, default='') # se pondran por defecto o a mano a futuro. 

    class Meta:
        db_table = 'zonas' # nombre de la coleccion mongodb relacionada a zona (comuna)

    def __str__(self):
        return self.nombre