import os.path

from aws_cdk.aws_s3_assets import Asset as S3asset

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets
)
from constructs import Construct

dirname = os.path.dirname(__file__)

class ServerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Web servers' security group: port 80 from anywhere
        web_sg = ec2.SecurityGroup(self, "WebServerSG", vpc=vpc)
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))

        # RDS security group: port 3306 only from the web servers' security group
        db_sg = ec2.SecurityGroup(self, "RdsSG", vpc=vpc)
        db_sg.add_ingress_rule(web_sg, ec2.Port.tcp(3306))

        # Instance Role and SSM Managed Policy
        InstanceRole = iam.Role(self, "InstanceSSM", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))

        InstanceRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))

        # Script in S3 as Asset
        webinitscriptasset = S3asset(self, "Asset", path=os.path.join(dirname, "configure.sh"))
        webinitscriptasset.grant_read(InstanceRole)

        # One web server in each public subnet
        web_instances = []
        for i, subnet in enumerate(vpc.public_subnets, start=1):
            cdk_lab_web_instance = ec2.Instance(self, f"cdk_lab_web_instance{i}", vpc=vpc,
                                                vpc_subnets=ec2.SubnetSelection(subnets=[subnet]),
                                                instance_type=ec2.InstanceType("t2.micro"),
                                                machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
                                                role=InstanceRole,
                                                security_group=web_sg)

            # Userdata executes script from S3
            asset_path = cdk_lab_web_instance.user_data.add_s3_download_command(
                bucket=webinitscriptasset.bucket,
                bucket_key=webinitscriptasset.s3_object_key
                )
            cdk_lab_web_instance.user_data.add_execute_file_command(
                file_path=asset_path
                )
            web_instances.append(cdk_lab_web_instance)

        # RDS MySQL instance with all private subnets as its subnet group
        rds.DatabaseInstance(self, "cdk_lab_rds",
                             engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0),
                             instance_type=ec2.InstanceType("t3.micro"),
                             vpc=vpc,
                             vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                             security_groups=[db_sg],
                             removal_policy=RemovalPolicy.DESTROY)  # so cdk destroy removes it

        # Load balancer that distributes requests to the web servers
        alb = elbv2.ApplicationLoadBalancer(self, "cdk_lab_alb", vpc=vpc, internet_facing=True)
        listener = alb.add_listener("HttpListener", port=80)
        alb.connections.allow_to(web_sg, ec2.Port.tcp(80))  # let the load balancer reach the web servers
        listener.add_targets("WebServers", port=80,
                             targets=[targets.InstanceTarget(inst, 80) for inst in web_instances])
