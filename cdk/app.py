#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_stack import CdkStack
import config



cdk_env = cdk.Environment(region=os.environ.get("REGION"), account=os.environ.get("ACCOUNT"))


app = cdk.App()

CdkStack(app, "ecsdjangoappstack",env=cdk_env)

app.synth()
