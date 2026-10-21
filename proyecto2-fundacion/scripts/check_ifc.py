import sys
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element

if len(sys.argv) != 2:
    raise SystemExit('Uso: python check_ifc.py foundation.ifc')

path = sys.argv[1]
model = ifcopenshell.open(path)
print('Schema:', model.schema)
print()

targets = [p for p in model.by_type('IfcProduct') if (getattr(p, 'Name', '') or '').startswith('Vertida_')]
if not targets:
    raise SystemExit('No encontre objetos con Name=Vertida_XX')

settings = ifcopenshell.geom.settings()
settings.set('use-world-coords', True)
mins, maxs = [], []
for p in sorted(targets, key=lambda x: x.Name):
    print('='*70)
    print('Name:', p.Name)
    print('Class:', p.is_a())
    print('GUID:', p.GlobalId)
    psets = ifcopenshell.util.element.get_psets(p)
    if psets:
        print('Property sets:')
        for k,v in psets.items():
            print(' ', k, v)
    else:
        print('Property sets: ninguno')
    try:
        shape = ifcopenshell.geom.create_shape(settings, p)
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1,3)
        lo = verts.min(axis=0)
        hi = verts.max(axis=0)
        mins.append(lo); maxs.append(hi)
        print('BBox min [m]:', np.round(lo,4))
        print('BBox max [m]:', np.round(hi,4))
        print('BBox size[m]:', np.round(hi-lo,4))
    except Exception as e:
        print('ERROR geometria:', e)
if mins:
    lo=np.min(np.vstack(mins),axis=0)
    hi=np.max(np.vstack(maxs),axis=0)
    print('\nGLOBAL')
    print('BBox min [m]:', np.round(lo,4))
    print('BBox max [m]:', np.round(hi,4))
    print('BBox size[m]:', np.round(hi-lo,4))
    print('\nNumero de vertidas:', len(targets))
