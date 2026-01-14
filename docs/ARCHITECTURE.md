# Workset Monitor Architecture

This document describes the architecture of the Daylily Workset Monitor system.

## System Overview

```mermaid
graph TB
    subgraph "Customer Portal"
        CP[Web UI]
        AUTH[AWS Cognito]
    end
    
    subgraph "API Layer"
        API[FastAPI REST API]
        VAL[Workset Validator]
        CUST[Customer Manager]
    end
    
    subgraph "Processing Layer"
        PROC[Concurrent Processor]
        SCHED[Workset Scheduler]
        NOTIF[Notification Manager]
    end
    
    subgraph "Data Layer"
        WDB[(Workset DynamoDB)]
        CDB[(Customer DynamoDB)]
        S3[(S3 Buckets)]
    end
    
    subgraph "Compute Layer"
        C1[Cluster 1]
        C2[Cluster 2]
        CN[Cluster N]
    end
    
    CP --> AUTH
    CP --> API
    AUTH --> API
    API --> VAL
    API --> CUST
    API --> WDB
    CUST --> CDB
    CUST --> S3
    VAL --> S3
    
    PROC --> SCHED
    PROC --> VAL
    PROC --> NOTIF
    PROC --> WDB
    SCHED --> WDB
    
    PROC --> C1
    PROC --> C2
    PROC --> CN
    
    C1 --> S3
    C2 --> S3
    CN --> S3
```

## Component Details

### 1. Customer Portal

**Purpose**: Self-service interface for customers

**Components**:
- Web UI (HTML/JavaScript)
- AWS Cognito for authentication
- JWT token management

**Features**:
- Customer registration
- Workset submission
- Status monitoring
- Usage tracking
- YAML generator

### 2. API Layer

**Purpose**: REST API for all operations

**Components**:
- FastAPI application
- Pydantic models for validation
- Authentication middleware
- CORS support

**Endpoints**:
- `/worksets/*` - Workset operations
- `/customers/*` - Customer management
- `/queue/stats` - Queue statistics
- `/scheduler/stats` - Scheduler statistics

### 3. Processing Layer

**Purpose**: Concurrent workset execution

**Components**:
- `ConcurrentWorksetProcessor`: Main processor
- `WorksetScheduler`: Cluster scheduling
- `NotificationManager`: Multi-channel notifications

**Features**:
- Thread pool execution
- Automatic retry with backoff
- Cluster affinity routing
- Load balancing

### 4. Data Layer

**Purpose**: Persistent storage

**Components**:
- Workset DynamoDB table
- Customer DynamoDB table
- S3 buckets (per-customer)

**Schema**:
- Workset records with state tracking
- Customer configurations
- Usage metrics

### 5. Compute Layer

**Purpose**: Execute worksets

**Components**:
- AWS ParallelCluster instances
- Slurm scheduler
- FSx for Lustre storage

**Features**:
- Auto-scaling
- Spot instance support
- Multi-AZ deployment

## Data Flow

### Workset Submission Flow

```mermaid
sequenceDiagram
    participant C as Customer
    participant API as API Layer
    participant VAL as Validator
    participant DB as DynamoDB
    participant S3 as S3
    
    C->>API: Submit workset
    API->>VAL: Validate config
    VAL->>S3: Check files
    S3-->>VAL: Files exist
    VAL-->>API: Validation result
    API->>DB: Register workset
    DB-->>API: Workset ID
    API-->>C: Submission confirmed
```

### Concurrent Processing Flow

```mermaid
sequenceDiagram
    participant PROC as Processor
    participant DB as DynamoDB
    participant SCHED as Scheduler
    participant CLUST as Cluster
    participant NOTIF as Notifications
    
    loop Every poll interval
        PROC->>DB: Get ready worksets
        DB-->>PROC: Workset list
        PROC->>SCHED: Schedule workset
        SCHED-->>PROC: Cluster assignment
        PROC->>DB: Update state to IN_PROGRESS
        PROC->>CLUST: Execute workset
        PROC->>NOTIF: Send started notification
        
        alt Success
            CLUST-->>PROC: Execution complete
            PROC->>DB: Update state to COMPLETED
            PROC->>NOTIF: Send completed notification
        else Failure
            CLUST-->>PROC: Execution failed
            PROC->>DB: Record failure
            alt Should retry
                PROC->>DB: Set state to RETRYING
                PROC->>NOTIF: Send retrying notification
            else No retry
                PROC->>DB: Set state to FAILED
                PROC->>NOTIF: Send failed notification
            end
        end
    end
```

### Retry Flow

```mermaid
sequenceDiagram
    participant PROC as Processor
    participant DB as DynamoDB
    participant CLUST as Cluster
    
    PROC->>DB: Get retryable worksets
    DB-->>PROC: Worksets past retry_after
    
    loop For each retryable
        PROC->>DB: Reset for retry
        DB-->>PROC: State reset to READY
        PROC->>CLUST: Execute workset
        
        alt Success
            CLUST-->>PROC: Complete
            PROC->>DB: State = COMPLETED
        else Failure
            CLUST-->>PROC: Failed
            PROC->>DB: Increment retry_count
            
            alt retry_count < max_retries
                PROC->>DB: State = RETRYING
                PROC->>DB: Set retry_after (exponential backoff)
            else Max retries exceeded
                PROC->>DB: State = FAILED
            end
        end
    end
```

## State Machine

```mermaid
stateDiagram-v2
    [*] --> REGISTERED: Submit workset
    REGISTERED --> READY: Validation passed
    REGISTERED --> FAILED: Validation failed
    
    READY --> LOCKED: Acquire lock
    LOCKED --> IN_PROGRESS: Start execution
    
    IN_PROGRESS --> COMPLETED: Success
    IN_PROGRESS --> RETRYING: Transient failure
    IN_PROGRESS --> FAILED: Permanent failure
    
    RETRYING --> READY: Retry time reached
    RETRYING --> FAILED: Max retries exceeded
    
    COMPLETED --> [*]
    FAILED --> [*]
```

## Cluster Affinity Routing

```mermaid
graph TB
    WS[Workset] --> SCHED[Scheduler]
    SCHED --> CHECK{Check Affinity}
    
    CHECK -->|Has affinity| ROUTE1[Route to specific cluster]
    CHECK -->|No affinity| EVAL[Evaluate options]
    
    EVAL --> LOC[Data Locality]
    EVAL --> COST[Cost Optimization]
    EVAL --> CAP[Capacity]
    
    LOC --> SCORE[Score clusters]
    COST --> SCORE
    CAP --> SCORE
    
    SCORE --> ROUTE2[Route to best cluster]
    
    ROUTE1 --> EXEC[Execute]
    ROUTE2 --> EXEC
```

## Scaling Considerations

### Horizontal Scaling

- **API Layer**: Multiple API instances behind load balancer
- **Processing Layer**: Multiple processor instances with distributed locking
- **Compute Layer**: Multiple clusters across regions/AZs

### Vertical Scaling

- **DynamoDB**: On-demand or provisioned capacity
- **S3**: Unlimited storage, request rate limits
- **Clusters**: Instance type and count per cluster

### Performance Targets

- **API Response Time**: < 100ms for reads, < 500ms for writes
- **Workset Throughput**: 10+ concurrent worksets per processor
- **Queue Depth**: Support 1000+ queued worksets
- **Retry Latency**: < 1 minute for first retry

## Security Architecture

```mermaid
graph TB
    subgraph "Public Internet"
        USER[User]
    end
    
    subgraph "AWS Account"
        subgraph "Public Subnet"
            ALB[Application Load Balancer]
            NAT[NAT Gateway]
        end
        
        subgraph "Private Subnet"
            API[API Servers]
            PROC[Processors]
            CLUST[Clusters]
        end
        
        subgraph "AWS Services"
            COGNITO[Cognito]
            DDB[DynamoDB]
            S3[S3]
        end
    end
    
    USER --> ALB
    ALB --> API
    API --> COGNITO
    API --> DDB
    API --> S3
    PROC --> DDB
    PROC --> S3
    PROC --> CLUST
    CLUST --> S3
    API --> NAT
    PROC --> NAT
```

## Monitoring and Observability

### Metrics

- Queue depth by state
- Workset processing rate
- Error rate by category
- Retry rate
- Cluster utilization
- API latency
- Customer usage

### Logging

- API access logs
- Workset execution logs
- Error logs with stack traces
- Audit logs for customer operations

### Alarms

- High error rate
- Queue depth threshold
- Cluster capacity
- API latency
- Failed authentication attempts

## See Also

- [Concurrent Processing](CONCURRENT_PROCESSING.md)
- [Customer Portal](CUSTOMER_PORTAL.md)
- [Feature Summary](FEATURE_SUMMARY.md)

