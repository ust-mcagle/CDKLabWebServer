# CDK Homework: Website on EC2 instances

Based on the lab [rclc/cdk-lab-web-server-spring-2026](https://github.com/rclc/cdk-lab-web-server-spring-2026).

## Stacks

**NetworkStack** (`cdk_lab_web_server/network_stack.py`)
- VPC `10.0.0.0/16` across 2 availability zones
- AZ 1: one public subnet + one private subnet
- AZ 2: one public subnet + one private subnet

**ServerStack** (`cdk_lab_web_server/server_stack.py`)
- One t2.micro web server (Amazon Linux 2) in each public subnet. User Data = `configure.sh`, uploaded as an S3 asset like the lab
- RDS MySQL 8.0 (db.t3.micro), subnet group = both private subnets
- Web server security group: TCP 80 from anywhere
- RDS security group: TCP 3306 from the web server security group only
- Internet-facing Application Load Balancer on port 80 that distributes requests to both web servers

## Setup (macOS)

```bash
brew install python awscli node
npm install -g aws-cdk
aws configure
aws sts get-caller-identity
```

## Deploy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap        # once per account/region
cdk synth
cdk deploy --all
```

(`source.bat` is a Windows helper from the lab template; it is not used on macOS.)

## Verify

```bash
# Load balancer DNS name, then request it several times (hostname alternates)
aws elbv2 describe-load-balancers --query "LoadBalancers[].DNSName" --output text
curl http://<load-balancer-dns-name>

# Both targets healthy
TG=$(aws elbv2 describe-target-groups --query "TargetGroups[0].TargetGroupArn" --output text)
aws elbv2 describe-target-health --target-group-arn $TG

# Web servers: one in each public subnet
aws ec2 describe-instances --filters Name=instance-state-name,Values=running \
  --query "Reservations[].Instances[].[InstanceId,PublicIpAddress,Placement.AvailabilityZone,SubnetId]" --output table
curl http://<web-server-public-ip>

# Subnets: 2 AZs, each with one public and one private subnet
VPC=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=NetworkStack/cdk_lab_vpc" --query "Vpcs[0].VpcId" --output text)
aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC \
  --query "Subnets[].[AvailabilityZone,CidrBlock,MapPublicIpOnLaunch]" --output table

# RDS MySQL in the private subnets, not publicly accessible
aws rds describe-db-instances \
  --query "DBInstances[].[Engine,DBInstanceStatus,PubliclyAccessible,DBSubnetGroup.Subnets[].SubnetIdentifier]"

# Security group rules
aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC \
  --query "SecurityGroups[].{Name:GroupName,In:IpPermissions}"
```

## Clean up

```bash
cdk destroy --all
```
