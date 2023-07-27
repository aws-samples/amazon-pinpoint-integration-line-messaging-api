#!/usr/bin/env python3

import aws_cdk as cdk

from part1.part1_stack import Part1Stack

app = cdk.App()
outbound_stack = Part1Stack(app, "part-1-stack")
app.synth()
