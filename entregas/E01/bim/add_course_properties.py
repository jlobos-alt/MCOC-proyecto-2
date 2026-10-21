import sys
import ifcopenshell
from ifcopenshell.api import pset

if len(sys.argv) != 3:
    raise SystemExit('Uso: python add_course_properties.py input.ifc output.ifc')

src, dst = sys.argv[1], sys.argv[2]
model = ifcopenshell.open(src)

defaults = {
    'Vertida_01': {'VertidaID': 1, 'Inicio_h': 0.0, 'TemperaturaColocacion_C': 18.0, 'TipoHormigon': 'M1'},
    'Vertida_02': {'VertidaID': 2, 'Inicio_h': 6.0, 'TemperaturaColocacion_C': 18.0, 'TipoHormigon': 'M1'},
    'Vertida_03': {'VertidaID': 3, 'Inicio_h': 12.0, 'TemperaturaColocaiton_C': 18.0, 'TipoHormigon': 'M1'},
    'Vertida_04': {'VertidaID': 4, 'Inicio_h': 18.0, 'TemperaturaColocacion_C': 18.0, 'TipoHormigon': 'M1'},
    'Vertida_05': {'VertidaID': 5, 'Inicio_h': 24.0, 'TemperaturaColocacion_C': 18.0, 'TipoHormigon': 'M1'},
}

products = {p.Name: p for p in model.by_type('IfcProduct') if getattr(p, 'Name', None)}
for name, props in defaults.items():
    product = products.get(name)
    if product is None:
        print(f'WARNING: no encontre {name}')
        continue
    pset = ifcopenshell.api.run('pset.add_pset', model, product=product, name='UANDES_HormigonMasivo')
    full = {**props, 'Moldaje': 'TBD', 'Aislacion': 'TBD', 'RetiroMoldaje_h': 72.0}
    ifcopenshell.api.run('pset.edit_pset', model, pset=pset, properties=full)
    print(f'OK: {name}')
model.write(dst)
print('Escrito:', dst)