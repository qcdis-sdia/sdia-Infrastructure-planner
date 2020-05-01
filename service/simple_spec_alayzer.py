import copy

from toscaparser.nodetemplate import NodeTemplate
from toscaparser.properties import Property

import networkx as nx
import logging

from service.specification_analyzer import SpecificationAnalyzer
from util import tosca_helper


def get_default_value(node_property):
    if node_property and node_property.required and isinstance(node_property.value, dict) and 'required' in \
            node_property.value and 'type' in node_property.value:
        if node_property.default:
            return {node_property.name: node_property.default}
        if node_property.constraints:
            for constraint in node_property.constraints:
                print(constraint)
    if node_property and node_property.required and node_property.value:
        return {node_property.name: node_property.value}
    return None


class SimpleAnalyzer(SpecificationAnalyzer):

    def __init__(self, tosca_template):
        super(SimpleAnalyzer, self).__init__(tosca_template)

    def set_relationship_occurrences(self):
        return_nodes = []
        orchestrator_nodes = tosca_helper.get_nodes_by_type('tosca.nodes.ARTICONF.docker.Orchestrator',
                                                            self.tosca_template.nodetemplates, self.all_node_types,
                                                            self.all_custom_def)
        min_masters_num = 1
        workers_num = 0
        if orchestrator_nodes:
            if 'properties' in orchestrator_nodes[0].entity_tpl:
                if 'min_masters_num' in orchestrator_nodes[0].entity_tpl['properties']:
                    min_masters_num = orchestrator_nodes[0].entity_tpl['properties']['min_masters_num']
                if 'min_workers_num' in orchestrator_nodes[0].entity_tpl['properties']:
                    workers_num = orchestrator_nodes[0].entity_tpl['properties']['min_workers_num']
            else:
                min_masters_num = orchestrator_nodes[0].get_property_value('min_masters_num')
                workers_num = orchestrator_nodes[0].get_property_value('min_workers_num')

        topology_nodes = tosca_helper.get_nodes_by_type('tosca.nodes.ARTICONF.VM.topology',
                                                        self.tosca_template.nodetemplates, self.all_node_types,
                                                        self.all_custom_def)
        if topology_nodes:
            vm_nodes = tosca_helper.get_nodes_by_type('tosca.nodes.ARTICONF.VM.Compute',
                                                      self.tosca_template.nodetemplates, self.all_node_types,
                                                      self.all_custom_def)
            if vm_nodes:
                for i in range(len(vm_nodes), min_masters_num):
                    old_vm_name = vm_nodes[0].name
                    new_vm = copy.deepcopy(vm_nodes[0])
                    new_vm_name = new_vm.name + '_' + str(i)
                    new_vm.name = new_vm_name
                    templates = new_vm.templates.pop(old_vm_name)
                    new_vm.templates[new_vm_name] = templates

                    return_nodes.append(new_vm)
                    for requirement in topology_nodes[0].requirements:
                        requirement_key = next(iter(requirement))
                        requirement_value = requirement[requirement_key]
                        if requirement_value['capability'] == 'tosca.capabilities.ARTICONF.VM':
                            new_requirement = copy.deepcopy(requirement)
                            new_requirement[requirement_key]['node'] = new_vm.name
                            topology_nodes[0].requirements.append(new_requirement)
                            return_nodes.append(topology_nodes[0])
                            break

                for i in range(len(vm_nodes), workers_num + 1):
                    old_vm_name = vm_nodes[0].name
                    new_vm = copy.deepcopy(vm_nodes[0])
                    new_vm_name = new_vm.name + '_' + str(i)
                    new_vm.name = new_vm_name
                    templates = new_vm.templates.pop(old_vm_name)
                    new_vm.templates[new_vm_name] = templates

                    return_nodes.append(new_vm)
                    for requirement in topology_nodes[0].requirements:
                        requirement_key = next(iter(requirement))
                        requirement_value = requirement[requirement_key]
                        if requirement_value['capability'] == 'tosca.capabilities.ARTICONF.VM':
                            new_requirement = copy.deepcopy(requirement)
                            new_requirement[requirement_key]['node'] = new_vm.name
                            topology_nodes[0].requirements.append(new_requirement)
                            return_nodes.append(topology_nodes[0])
                            break

        return return_nodes

    def set_node_specifications(self):
        nodes = []
        for node_template in self.tosca_template.nodetemplates:
            nodes.append(self.set_default_node_properties(node_template))
        return nodes

    # def set_default_node_properties(self, node):
    #     logging.info('Setting properties for: ' + str(node.type))
    #     ancestors_properties = tosca_helper.get_all_ancestors_properties(node, self.all_node_types,
    #                                                                      self.all_custom_def)
    #     default_properties = {}
    #     for ancestors_property in ancestors_properties:
    #         default_property = get_default_value(ancestors_property)
    #         if default_property:
    #             default_properties[next(iter(default_property))] = default_property[next(iter(default_property))]
    #
    #     if default_properties:
    #         for default_property in default_properties:
    #             node.get_properties_objects().append(default_property)
    #         node_name = next(iter(node.templates))
    #         if 'properties' in node.templates[node_name]:
    #             for prop_name in node.templates[node_name]['properties']:
    #                 if isinstance(node.templates[node_name]['properties'][prop_name], dict) or \
    #                         isinstance(node.templates[node_name]['properties'][prop_name], str):
    #                     if 'required' in node.templates[node_name]['properties'][prop_name] and \
    #                             node.templates[node_name]['properties'][prop_name]['required'] and \
    #                             'default' in node.templates[node_name]['properties'][prop_name] and \
    #                             prop_name not in default_properties:
    #                         default_properties[prop_name] = node.templates[node_name]['properties'][prop_name][
    #                             'default']
    #
    #         logging.info(
    #             'Adding to : ' + str(node.templates[node_name]) + ' properties: ' + str(default_properties))
    #         node.templates[node_name]['properties'] = default_properties
    #     return node
