from aws_cdk import (
    # Duration,
    Stack,
    RemovalPolicy,
    Duration
    # aws_sqs as sqs,
)
from aws_cdk import RemovalPolicy, CfnOutput
from constructs import Construct
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_certificatemanager as certificate
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_elasticloadbalancingv2 as elb
import aws_cdk.aws_certificatemanager as acm
import aws_cdk.aws_rds as rds
import aws_cdk.aws_secretsmanager as secretsmanager
import aws_cdk.aws_route53_targets as targets
import  aws_cdk.aws_s3 as s3
import aws_cdk.aws_route53 as route53
import json 
from config import (
    djangoconf
    
    )

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        vpc = ec2.Vpc.from_lookup(self, "ImportedVpc",vpc_id=djangoconf['vpcid'] )
    
        # Route53 record
        zone = route53.HostedZone.from_hosted_zone_attributes(self,'Route53HostedZone',
            hosted_zone_id=djangoconf['zone_id'],
           zone_name=djangoconf['domaine']
        )
        
        # Acm Certificate
        certificate = acm.Certificate.from_certificate_arn(self, "domainCert", djangoconf["certificatearn"])
        
        # Loadbalancer sg
        alb_sg = ec2.SecurityGroup(self, "ALBSSG",
           vpc = vpc,
           security_group_name="alb-sg",
           allow_all_outbound=True,
        )
        
        alb_sg.add_ingress_rule(
            ec2.Peer.ipv4('0.0.0.0/0'),
            ec2.Port.tcp(80)
        )
        
        alb_sg.add_ingress_rule(
            ec2.Peer.ipv4('0.0.0.0/0'),
            ec2.Port.tcp(443)
        )
        # Application Loadbalancer
        alb = elb.ApplicationLoadBalancer(self, "AWSALBECS",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name=djangoconf["alb-name"],
            security_group= alb_sg,
            vpc_subnets=ec2.SubnetSelection(
                    subnet_type = ec2.SubnetType.PUBLIC
                ),
            
        )
        
        # Alias Record
        route53.ARecord(self, "AliasRecord",
            zone=zone,
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(alb)),
            record_name=djangoconf["record"]
        )
        
        # ECS Cluster
        cluster = ecs.Cluster.from_cluster_attributes(self, "ECSCluster",
                vpc=vpc,
                cluster_name=djangoconf['name'],
            )
            
        # task role and excecution role  
        taskrole = iam.Role(self, "Role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            role_name="aws-ecs-task-role",
            managed_policies=[
                  iam.ManagedPolicy.from_aws_managed_policy_name("AWSXrayFullAccess"),
                  iam.ManagedPolicy.from_aws_managed_policy_name("AmazonPrometheusFullAccess"),
                ]
        )
        
        taskexecutionRolePolicy = iam.PolicyStatement( 
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:getauthorizationtoken",
                "ecr:batchchecklayeravailability",
                "ecr:getdownloadurlforlayer",
                "ecr:batchgetimage",
                "logs:createlogstream",
                "logs:putlogevents"
            ],
            resources=["*"]
        )
        
        # django ecs task definition
        apptaskDef = ecs.TaskDefinition(self, "djangoTaskDefinition",
              compatibility=ecs.Compatibility.FARGATE,
              family=djangoconf["family"],
              task_role=taskrole,
              cpu="1024",
              memory_mib="2048"
            )
        
        apptaskDef.add_to_execution_role_policy(taskexecutionRolePolicy)
        
        apptaskDef.add_container("DjangoContainer",
              container_name="django",
              image=ecs.ContainerImage.from_asset(
                   "../djangoproject" 
                 ),
              memory_reservation_mib= 2048,
              cpu= 1024,
              health_check=ecs.HealthCheck(
                    command=["CMD-SHELL", "curl -f http://127.0.0.1:8000/ping/ || exit 1"],
                    # the properties below are optional
                    # interval=Duration.seconds(60),
                    retries=3,
                    # start_period=Duration.seconds(120),
                    # timeout=Duration.seconds(60)
                ),
              port_mappings=[
                  ecs.PortMapping(
                      container_port=8000,
                      protocol=ecs.Protocol.TCP
                  )
              ],
              logging= ecs.LogDriver.aws_logs(
                    stream_prefix="ecs-djangoapp"
                  )
            )
            
        # django application security group
        
        app_ecs_service_sg = ec2.SecurityGroup(self, "djangoServiceSG",
           vpc = vpc,
           security_group_name=djangoconf["sg-name"],
           allow_all_outbound=True,
        )
        
        appfargateService = ecs.FargateService(self,
                "djangoEcsService",
                service_name=djangoconf["svc-name"],
                cluster=cluster,
                assign_public_ip=True,
                enable_execute_command=True,
                security_groups= [app_ecs_service_sg],
                task_definition=apptaskDef,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type = ec2.SubnetType.PUBLIC
                )
                
            )
            
        httplist = alb.add_listener("AWSAlbListenerHttp",
          port=80,
        )
        
        httplist.add_targets(
            "HttpTarget",
              port=80,
              targets= [
                  appfargateService.load_balancer_target(container_name="django", container_port=8000, protocol=ecs.Protocol.TCP)
                ]
            )
            
        httpslist = alb.add_listener("AWSAlbListenerHttps",
         port=443,
         certificates= [certificate],
        )
        
        httpslist.add_targets("HttpsTarget",
               port=80,
               targets= [
                  appfargateService.load_balancer_target(container_name="django", container_port=8000, protocol=ecs.Protocol.TCP)
                 ]
            )

        
        