#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_lab_web_server.network_stack import NetworkStack
from cdk_lab_web_server.server_stack import ServerStack


app = cdk.App()
network_stack = NetworkStack(app, "NetworkStack")
ServerStack(app, "ServerStack", vpc=network_stack.vpc)

app.synth()
