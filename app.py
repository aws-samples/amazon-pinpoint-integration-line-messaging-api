#!/usr/bin/env python3

import aws_cdk as cdk

from part1.part1_stack import Part1Stack
from cdk_nag import AwsSolutionsChecks

app = cdk.App()
cdk.Aspects.of(app).add(AwsSolutionsChecks())
outbound_stack = Part1Stack(app,"part-1-stack")
app.synth()