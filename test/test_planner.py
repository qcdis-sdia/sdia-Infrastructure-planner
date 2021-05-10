import copy
import json
import logging
import os
import os.path
import tempfile
import time
import unittest
from urllib.parse import urlparse

import requests
import yaml
from toscaparser.tosca_template import ToscaTemplate

from planner.planner import Planner
from service.spec_service import SpecService
from util import tosca_helper

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MyTestCase(unittest.TestCase):


    def test_helm(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/helm.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)


    def test_openstack(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/openstack.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)

    def test_tic_gluster_fs(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/glusterFS.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)


    def test_tic(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/TIC.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)


    def test_docker(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/application_example_updated.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)

        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/lifeWatch_vre1.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)



    def test_topology(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/topology.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)

    def test_compute(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/compute.yaml'
        input_tosca_file_path = self.get_remote_tosca_file(url)
        self.run_test(input_tosca_file_path)

    def test_lifeWatch(self):
        url = 'https://raw.githubusercontent.com/qcdis-sdia/sdia-tosca/master/examples/lifeWatch_vre1.yaml'
        tic_tosca = requests.get(url)
        input_tosca_file_path = os.path.join(tempfile.gettempdir(),'TIC.yaml')
        open( input_tosca_file_path, 'wb').write(tic_tosca.content)
        self.run_test(input_tosca_file_path)

    def get_input_tosca_file_path(self, file_name):
        tosca_path = "../../TOSCA/"
        input_tosca_file_path = tosca_path + file_name
        if not os.path.exists(input_tosca_file_path):
            tosca_path = "../TOSCA/"
            input_tosca_file_path = tosca_path + file_name

        self.assertEqual(True, os.path.exists(input_tosca_file_path),
                         "Input TOSCA file: " + input_tosca_file_path + " not found")
        return input_tosca_file_path

    def run_test(self, input_tosca_file_path):
        conf = {'url': "http://host"}
        spec_service = SpecService(conf)
        test_planner = Planner(input_tosca_file_path, spec_service)
        test_tosca_template = test_planner.resolve_requirements()
        template_dict = tosca_helper.get_tosca_template_2_topology_template_dictionary(test_tosca_template)
        test_tosca_template = test_planner.set_node_templates_properties()

        template_dict = tosca_helper.get_tosca_template_2_topology_template_dictionary(test_tosca_template)
        logger.info("template ----: \n" + yaml.dump(template_dict))
        print(yaml.dump(template_dict))
        ToscaTemplate(yaml_dict_tpl=copy.deepcopy(template_dict))

        test_response = {'toscaTemplate': template_dict}

        response = {'toscaTemplate': template_dict}
        output_current_milli_time = int(round(time.time() * 1000))
        response["creationDate"] = output_current_milli_time
        response["parameters"] = []
        # print("Output message:" + json.dumps(response))
        self.assertEqual(True, True)

    def get_remote_tosca_file(self, url):
        tosca = requests.get(url)
        a = urlparse(url)
        input_tosca_file_path = os.path.join(tempfile.gettempdir(),os.path.basename(a.path))
        open( input_tosca_file_path, 'wb').write(tosca.content)
        return input_tosca_file_path
