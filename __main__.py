# To change this license header, choose License Headers in Project Properties.
# To change this template file, choose Tools | Templates
# and open the template in the editor.
import json
import os
import os.path
import tempfile
import time
import logging
from concurrent.futures import thread
from threading import Thread

import pika
import toscaparser
import yaml
import sys
import copy

from time import sleep

from toscaparser.tosca_template import ToscaTemplate

from planner.planner import Planner
from service.spec_service import SpecService
from util import tosca_helper

logger = logging.getLogger(__name__)

# if not getattr(logger, 'handler_set', None):
# logger.setLevel(logging.INFO)
# h = logging.StreamHandler()
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# h.setFormatter(formatter)
# logger.addHandler(h)
# logger.handler_set = True

done = False


def init_chanel(args):
    global rabbitmq_host
    if len(args) > 1:
        rabbitmq_host = args[1]
        queue_name = args[2]  # planner
    else:
        rabbitmq_host = '127.0.0.1'

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name)
    return channel, connection


def start(this_channel):
    this_channel.basic_qos(prefetch_count=1)
    this_channel.basic_consume(queue=queue_name, on_message_callback=on_request)
    logger.info(" [x] Awaiting RPC requests")
    this_channel.start_consuming()


def on_request(ch, method, props, body):
    response = handle_delivery(body)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id=
                                                     props.correlation_id),
                     body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def handle_delivery(message, sys=None):
    logger.info("Got: " + str(message))
    try:
        message = message.decode()
    except (UnicodeDecodeError, AttributeError):
        e = sys.exc_info()[0]
        logger.info("Parsing Error: " + str(e))
    parsed_json_message = json.loads(message)
    owner = parsed_json_message['owner']
    tosca_file_name = 'tosca_template'
    tosca_template_json = parsed_json_message['toscaTemplate']

    input_current_milli_time = lambda: int(round(time.time() * 1000))

    # rabbit = DRIPLoggingHandler(host=rabbitmq_host, port=5672, user=owner)
    # logger.addHandler(rabbit)

    try:
        tosca_folder_path = os.path.join(tempfile.gettempdir(), "planner_files", str(input_current_milli_time()))
    except NameError:
        import sys
        millis = int(round(time.time() * 1000))
        tosca_folder_path = os.path.dirname(os.path.abspath(sys.argv[0])) + os.path.join(tempfile.gettempdir(),
                                                                                         "planner_files",
                                                                                         str(millis))

    if not os.path.exists(tosca_folder_path):
        os.makedirs(tosca_folder_path)
    input_tosca_file_path = os.path.join(tosca_folder_path, tosca_file_name + ".yml")
    with open(input_tosca_file_path, 'w') as outfile:
        outfile.write(yaml.dump(tosca_template_json))

    conf = {'url': "http://host"}
    spec_service = SpecService(conf)
    try:
        planner = Planner(tosca_path=input_tosca_file_path, spec_service=spec_service)
        tosca_template = planner.resolve_requirements()
        tosca_template = planner.set_node_templates_properties()
        template_dict = tosca_helper.get_tosca_template_2_topology_template_dictionary(tosca_template)

        Planner(yaml_dict_tpl=template_dict, spec_service=spec_service)

        if hasattr(planner, 'workflows') and  planner.workflows:
            template_dict['topology_template']['workflows'] = planner.workflows

        logger.info("template ----: \n" + yaml.dump(template_dict))
        response = {'toscaTemplate': template_dict}
    except Exception as ex:
        response = {'error': ex.message}


    output_current_milli_time = int(round(time.time() * 1000))
    response["creationDate"] = output_current_milli_time
    if queue_name == "planner_queue":
        logger.info("Planning")
    logger.info("Returning plan")
    logger.info("Output message:" + json.dumps(response))
    return json.dumps(response)


def threaded_function(args):
    while not done:
        connection.process_data_events()
        sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if sys.argv[1] == "test_local":
        tosca_path = "../TOSCA/"
        input_tosca_file_path = tosca_path + '/application_example_updated.yaml'
        conf = {'url': "http://host"}
        spec_service = SpecService(conf)
        test_planner = Planner(input_tosca_file_path, spec_service)
        test_tosca_template = test_planner.resolve_requirements()
        test_tosca_template = test_planner.set_node_templates_properties()
        template_dict = tosca_helper.get_tosca_template_2_topology_template_dictionary(test_tosca_template)
        logger.info("template ----: \n" + yaml.dump(template_dict))

        ToscaTemplate(yaml_dict_tpl=copy.deepcopy(template_dict))

        test_response = {'toscaTemplate': template_dict}
        logger.info("Output message:" + json.dumps(test_response))
    else:
        logger.info("Input args: " + sys.argv[0] + ' ' + sys.argv[1] + ' ' + sys.argv[2])
        global channel
        global connection
        channel, connection = init_chanel(sys.argv)
        global queue_name
        queue_name = sys.argv[2]

        # thread = Thread(target=threaded_function, args=(1,))
        # thread.start()

        logger.info("Awaiting RPC requests")
        try:
            start(channel)
        except Exception as e:
            e = sys.exc_info()[0]
            logger.info("Error: " + str(e))
            print(e)
            exit(-1)
