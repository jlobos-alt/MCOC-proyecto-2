import ifcopenshell
import ifcopenshell.api

model = ifcopenshell.file(schema='IFC4')
project = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcProject', name='Proyecto2')
site = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcSite', name='Site')
building = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcBuilding', name='Building')
storey = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcBuildingStorey', name='Storey')
ifcopenshell.api.run('aggregate.assign_object', model, products=[site], relating_object=project)
ifcopenshell.api.run('aggregate.assign_object', model, products=[building], relating_object=site)
ifcopenshell.api.run('aggregate.assign_object', model, products=[storey], relating_object=building)

for name in ['Vertida_01','Vertida_02','Vertida_03','Vertida_04','Vertida_05']:
    foot = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcFooting', name=name)
    ifcopenshell.api.run('spatial.assign_container', model, relating_structure=storey, products=[foot])

out = r'C:/Users/josel/OneDrive/Escritorio/MCOC/proyecto2-fundacion/ifc/foundation.ifc'
model.write(out)