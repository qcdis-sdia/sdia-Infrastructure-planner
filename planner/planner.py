import logging

import yaml
from toscaparser.nodetemplate import NodeTemplate
from toscaparser.tosca_template import ToscaTemplate
from toscaparser.topology_template import TopologyTemplate

import operator

from service.simple_spec_alayzer import SimpleAnalyzer
from util import tosca_helper

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def add_requirements(node, missing_requirements, capable_node_name):
    """Add the requirements to the node """
    for req in missing_requirements:
        req[next(iter(req))]['node'] = capable_node_name
        if isinstance(node, NodeTemplate):
            contains_requirement = False
            for node_requirement in node.requirements:
                if node_requirement == req:
                    contains_requirement = True
                    break
            if not contains_requirement:
                node.requirements.append(req)
        elif isinstance(node, dict):
            type_name = next(iter(node))
            if 'requirements' not in node[type_name]:
                node[type_name]['requirements'] = []
            node_requirements = node[type_name]['requirements']
            contains_requirement = False
            for node_requirement in node_requirements:
                if node_requirement == req:
                    contains_requirement = True
                    break
            if not contains_requirement:
                node[type_name]['requirements'].append(req)
    return node


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


class Planner:

    def __init__(self, tosca_path=None, yaml_dict_tpl=None, spec_service=None):
        if tosca_path:
            self.path = tosca_path
            self.tosca_template = ToscaTemplate(tosca_path)
        elif yaml_dict_tpl:
            self.yaml_dict_tpl = yaml_dict_tpl
            logger.info('yaml_dict_tpl:\n' + str(yaml.dump(yaml_dict_tpl)))
            self.tosca_template = ToscaTemplate(yaml_dict_tpl=yaml_dict_tpl)

        self.tosca_node_types = self.tosca_template.nodetemplates[0].type_definition.TOSCA_DEF
        self.all_custom_def = self.tosca_template.nodetemplates[0].custom_def
        self.all_node_types = {}
        self.all_node_types.update(self.tosca_node_types.items())
        self.all_node_types.update(self.all_custom_def.items())
        self.required_nodes = []

        self.spec_service = spec_service

    def add_required_nodes_to_template(self, required_nodes):
        for req_node in required_nodes:
            node_template = tosca_helper.node_type_2_node_template(req_node, self.all_custom_def)
            self.tosca_template.nodetemplates.append(node_template)
        return self.tosca_template

    def set_default_node_properties(self, node):
        logger.info('Setting properties for: ' + str(node.type))
        ancestors_properties = tosca_helper.get_all_ancestors_properties(node, self.all_node_types,
                                                                         self.all_custom_def)
        default_properties = {}
        if ancestors_properties:
            for ancestors_property in ancestors_properties:
                for node_prop in node.get_properties_objects():
                    if ancestors_property.name == node_prop.name and isinstance(node_prop.value,dict) \
                            and 'required' in node_prop.value and 'type' in node_prop.value:
                        default_property = get_default_value(ancestors_property)
                        if default_property:
                            node_prop.value = default_property
                            default_properties[next(iter(default_property))] = default_property[
                                next(iter(default_property))]
        if default_properties:
            for default_property in default_properties:
                for node_prop_obj in node.get_properties_objects():
                    if default_property == node_prop_obj.name and not node_prop_obj.value:
                        node.get_properties_objects().append(default_property)

            node_name = next(iter(node.templates))
            if 'properties' in node.templates[node_name]:
                for prop_name in node.templates[node_name]['properties']:
                    if isinstance(node.templates[node_name]['properties'][prop_name], dict) or \
                            isinstance(node.templates[node_name]['properties'][prop_name], str):
                        if 'required' in node.templates[node_name]['properties'][prop_name] and \
                                node.templates[node_name]['properties'][prop_name]['required'] and \
                                'default' in node.templates[node_name]['properties'][prop_name] and \
                                prop_name not in default_properties:
                            default_properties[prop_name] = node.templates[node_name]['properties'][prop_name][
                                'default']

            logger.info(
                'Adding to : ' + str(node.templates[node_name]) + ' properties: ' + str(default_properties))
            node.templates[node_name]['properties'] = default_properties
        return node

    def set_node_templates_properties(self):
        for node_template in self.tosca_template.nodetemplates:
            self.set_default_node_properties(node_template)

        specification_analyzer = SimpleAnalyzer(self.tosca_template)
        nodes_with_new_relationship_occurrences = specification_analyzer.set_relationship_occurrences()

        added_node_names = []
        for new_spec_occurrences in nodes_with_new_relationship_occurrences:
            for index, node_in_temple in enumerate(self.tosca_template.nodetemplates):
                if new_spec_occurrences.name == node_in_temple.name:
                    added_node_names.append(new_spec_occurrences.name)
                    self.tosca_template.nodetemplates[index] = new_spec_occurrences
                    break

        for new_spec_occurrences in nodes_with_new_relationship_occurrences:
            if new_spec_occurrences.name not in added_node_names:
                self.tosca_template.nodetemplates.append(new_spec_occurrences)
        return self.tosca_template


    def get_node_template_property(self, prop_key, node_prop_dict):
        prop_value = self.spec_service.get_property(prop_key)
        if prop_value:
            return {prop_key: node_prop_dict}
        else:
            if 'required' in node_prop_dict and 'default' in node_prop_dict:
                return node_prop_dict['default']
            if 'constraints' in node_prop_dict:
                constraints = node_prop_dict['constraints']
                for constraint in constraints:

                    if next(iter(constraint)) == 'greater_or_equal':
                        return constraint[next(iter(constraint))]
            return None

    def resolve_requirements(self):
        """ Resolve requirements. Go over all nodes and recursively resolve requirements till node has no
        requirements  e.g. docker -> k8s -> cluster -> vm """
        for node in self.tosca_template.nodetemplates:
            self.add_interfaces(node)
            self.add_required_nodes(node)
        return self.add_required_nodes_to_template(self.required_nodes)

    def add_required_nodes(self, node):
        """Adds the required nodes in self.required_nodes for an input node."""
        if isinstance(node, NodeTemplate):
            logger.info('Resolving requirements for: ' + node.name)
        elif isinstance(node, dict):
            logger.info('Resolving requirements for: ' + str(next(iter(node))))
        # Get all requirements for node.
        all_requirements = self.get_all_requirements(node)
        if not all_requirements:
            logger.debug('Node: ' + tosca_helper.get_node_type_name(node) + ' has no requirements')
            return
        matching_node = self.find_best_node_for_requirements(all_requirements)

        # Only add node that is not in node_templates
        matching_node_type_name = next(iter(matching_node))
        matching_node_template = tosca_helper.node_type_2_node_template(matching_node, self.all_custom_def)
        # Add the requirements to the node we analyzed. e.g. docker needed host now we added the type and name of host
        node = add_requirements(node, all_requirements, matching_node_template.name)
        if not tosca_helper.contains_node_type(self.required_nodes, matching_node_type_name) and \
                not tosca_helper.contains_node_type(self.tosca_template.nodetemplates, matching_node_type_name):
            logger.info('  Adding: ' + str(matching_node_template.name))
            self.required_nodes.append(matching_node)
        # Find matching nodes for the new node's requirements
        self.add_required_nodes(matching_node)

    def get_all_requirements(self, node):
        """Returns  all requirements for an input node including all parents requirements"""

        node_type_name = tosca_helper.get_node_type_name(node)
        logger.info('      Looking for requirements for node: ' + node_type_name)
        # Get the requirements for this node from its definition e.g. docker: hostedOn k8s
        def_type = self.all_node_types[node_type_name]
        all_requirements = []
        if 'requirements' in def_type.keys():
            all_requirements = def_type['requirements']
            logger.info('      Found requirements: ' + str(all_requirements) + ' for node: ' + node_type_name)

        # Get the requirements for this node from the template. e.g. wordpress: connectsTo mysql
        # node_requirements =  tosca_helper.get_node_requirements(node)
        # if node_requirements:
        #     all_requirements += node_requirements

        # Put them all together
        parent_requirements = tosca_helper.get_ancestors_requirements(node, self.all_node_types, self.all_custom_def)
        parent_type = tosca_helper.get_node_type_name(node)
        if parent_type and parent_requirements:
            logger.info(
                '       Adding to : ' + str(node_type_name) + '  parent requirements from: ' + str(parent_type))
            if not all_requirements:
                all_requirements += parent_requirements
            else:
                for all_requirement in all_requirements:
                    for parent_requirement in parent_requirements:
                        all_requirement_key = next(iter(all_requirement))
                        parent_requirement_key = next(iter(parent_requirement))
                        if all_requirement_key != parent_requirement_key and all_requirement[all_requirement_key][
                            'capability'] != parent_requirement[parent_requirement_key]['capability']:
                            all_requirements.append(parent_requirement)

            logger.debug('      all_requirements: ' + str(all_requirements))
        return all_requirements

    def get_node_types_by_capability(self, cap):
        """Returns  all nodes that have the  capability: cap and have interfaces. This way we  distinguish between
        'abstract' and 'concrete' """
        candidate_nodes = {}
        for tosca_node_type in self.all_node_types:
            if tosca_node_type.startswith('tosca.nodes') and 'capabilities' in self.all_node_types[tosca_node_type]:
                logger.debug('      Node: ' + str(tosca_node_type))
                for caps in self.all_node_types[tosca_node_type]['capabilities']:
                    logger.debug('          ' + str(
                        self.all_node_types[tosca_node_type]['capabilities'][caps]['type']) + ' == ' + cap)
                    if self.all_node_types[tosca_node_type]['capabilities'][caps]['type'] == cap:
                        candidate_nodes[tosca_node_type] = self.all_node_types[tosca_node_type]
                        logger.debug('          candidate_node: ' + str(tosca_node_type))

        candidate_child_nodes = {}
        for node in candidate_nodes:
            candidate_child_nodes.update(self.get_child_nodes(node))

        candidate_nodes.update(candidate_child_nodes)
        capable_nodes = {}
        # Only return the nodes that have interfaces. This means that they are not "abstract"
        nodes_type_names_with_interface = tosca_helper.get_node_types_with_interface(candidate_nodes)
        for type_name in nodes_type_names_with_interface:
            capable_nodes[type_name] = candidate_nodes[type_name]
        return capable_nodes

    def find_best_node_for_requirements(self, all_requirements):
        """Returns  the 'best' node for a set of requirements. Here we count the number of requiremets that the node
        can cover and return the one which covers the most """
        matching_nodes = {}
        number_of_matching_requirement = {}
        # Loop requirements to find nodes per requirement
        for req in all_requirements:
            if 'capability' in req[next(iter(req))]:
                capability = req[next(iter(req))]['capability']
                # Find all nodes in the definitions that have the capability: capability
                logger.info('  Looking for nodes in node types with capability: ' + capability)
                capable_nodes = self.get_node_types_by_capability(capability)
                if capable_nodes:
                    # Add number of matching capabilities for each node.
                    # Try to score matching_nodes to return one. The more requirements a node meets the better
                    for node_type in capable_nodes:
                        matching_requirement_count = 1
                        if node_type not in number_of_matching_requirement:
                            number_of_matching_requirement[node_type] = matching_requirement_count
                        else:
                            matching_requirement_count = number_of_matching_requirement[node_type]
                            matching_requirement_count += 1

                        number_of_matching_requirement[node_type] = matching_requirement_count
                        logger.info('      Found: ' + str(node_type))
                    matching_nodes.update(capable_nodes)
                else:
                    logger.error('Did not find any node with required capability: ' + str(capability))
                    raise Exception('Did not find any node with required capability: ' + str(capability))
        # if we only found 1 return it
        if len(matching_nodes) == 1:
            return matching_nodes

        sorted_number_of_matching_requirement = sorted(number_of_matching_requirement.items(),
                                                       key=operator.itemgetter(1))
        index = len(sorted_number_of_matching_requirement) - 1
        winner_type = next(iter(sorted_number_of_matching_requirement[index]))
        return {winner_type: matching_nodes[winner_type]}

    def get_child_nodes(self, parent_node_type_name):
        child_nodes = {}
        for tosca_node_type in self.all_node_types:
            if tosca_node_type.startswith('tosca.nodes') and 'derived_from' in self.all_node_types[tosca_node_type]:
                if parent_node_type_name == self.all_node_types[tosca_node_type]['derived_from']:
                    child_nodes[tosca_node_type] = self.all_node_types[tosca_node_type]
        return child_nodes

    def add_interfaces(self, node):
        # node_type_interfaces = tosca_helper.get_node_type_interfaces(node)
        # node_template_interfaces = tosca_helper.get_node_template_interfaces(node)
        # if not node_template_interfaces and node_type_interfaces:
        #     tosca_helper.add_interfaces(node,node_type_interfaces)
        return node
