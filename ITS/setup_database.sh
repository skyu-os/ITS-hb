#!/bin/bash

# 数据库部署配置脚本
# 适用于Railway + PostgreSQL + Supabase

echo "=== ITS智能交通系统 - 海外数据库配置 ==="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查环境
check_env() {
    echo -e "${YELLOW}检查部署环境...${NC}"
    
    # 检查是否在正确的目录
    if [[ ! -f "backend/enhanced_server.py" ]]; then
        echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
        exit 1
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 需要安装Python3${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}环境检查通过${NC}"
}

# 安装依赖
install_deps() {
    echo -e "${YELLOW}安装数据库依赖...${NC}"
    pip3 install sqlalchemy psycopg2-binary alembic
    echo -e "${GREEN}依赖安装完成${NC}"
}

# 创建PostgreSQL配置
create_postgres_config() {
    echo -e "${YELLOW}创建PostgreSQL配置...${NC}"
    
    # 创建环境变量文件
    cat > backend/.env.production << EOL
# PostgreSQL 配置
DATABASE_URL=postgresql://\${POSTGRES_USER}:\${POSTGRES_PASSWORD}@\${POSTGRES_HOST}:\${POSTGRES_PORT}/\${POSTGRES_DB}
POSTGRES_USER=traffic_user
POSTGRES_PASSWORD=traffic_secure_pass_2024
POSTGRES_DB=traffic_db
POSTGRES_HOST=db.railway.com
POSTGRES_PORT=5432

# Redis 配置
REDIS_URL=redis://\${REDIS_HOST}:\${REDIS_PORT}
REDIS_HOST=redis.railway.com
REDIS_PORT=6379

# 高德API配置
AMAP_API_KEY=\${AMAP_API_KEY}
AMAP_WEB_KEY=\${AMAP_WEB_KEY}

# 应用配置
API_SECRET=traffic-prediction-secret-key-2024
ENVIRONMENT=production
CORS_ORIGINS=https://its-traffic.vercel.app,http://localhost:3000
EOL

    # 更新数据库配置
    cat > backend/database_production.py << EOL
"""生产环境数据库配置"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis

# 数据库URL
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://traffic_user:traffic_secure_pass_2024@db.railway.com:5432/traffic_db'
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=False
)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型
Base = declarative_base()

# Redis配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis.railway.com:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
EOL

    echo -e "${GREEN}PostgreSQL配置创建完成${NC}"
}

# 创建数据库模型迁移脚本
create_migration() {
    echo -e "${YELLOW}创建数据库迁移脚本...${NC}"
    
    # 创建迁移配置
    cat > backend/alembic.ini << EOL
# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = migrations

# template used to generate migration file names; The default value is %%(rev)s_%%(slug)s
# Uncomment the line below if you want the files to be prepended with date and time
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the python-dateutil library that can be
# installed by adding `alembic[tz]` to the pip requirements
# string value is passed to dateutil.tz.gettz()
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version number format
# version_num_format = %%(revision)s

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = postgresql://traffic_user:traffic_secure_pass_2024@db.railway.com:5432/traffic_db

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOL

    # 创建迁移目录结构
    mkdir -p backend/migrations/versions
    mkdir -p backend/migrations/script.py.mako

    # 创建迁移脚本模板
    cat > backend/migrations/script.py.mako << EOL
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
EOL

    echo -e "${GREEN}数据库迁移脚本创建完成${NC}"
}

# 创建Supabase配置
create_supabase_config() {
    echo -e "${YELLOW}创建Supabase配置...${NC}"
    
    cat > backend/database_supabase.py << EOL
"""Supabase数据库配置"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid
import redis

# Supabase配置
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY', 'your-anon-key')

# 数据库URL
DATABASE_URL = f"postgresql://postgres:{SUPABASE_KEY}@{SUPABASE_URL.replace('https://', '').split('.')[0]}.supabase.co:5432/postgres"

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=False
)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型
Base = declarative_base()

# Redis配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
EOL

    echo -e "${GREEN}Supabase配置创建完成${NC}"
}

# 创建部署脚本
create_deploy_script() {
    echo -e "${YELLOW}创建数据库部署脚本...${NC}"
    
    cat > deploy_database.sh << EOL
#!/bin/bash

# 数据库部署脚本
# 支持Railway和Supabase

set -e

echo "=== 开始部署数据库配置 ==="

# 选择数据库平台
echo "选择数据库平台:"
echo "1) Railway PostgreSQL"
echo "2) Supabase"
read -p "请选择 (1/2): " choice

case $choice in
    1)
        echo "部署到Railway..."
        cp backend/database_production.py backend/database.py
        echo "✅ Railway配置已启用"
        ;;
    2)
        echo "部署到Supabase..."
        cp backend/database_supabase.py backend/database.py
        echo "✅ Supabase配置已启用"
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

# 初始化数据库
echo "初始化数据库..."
alembic upgrade head

# 验证连接
echo "验证数据库连接..."
python3 -c "
from backend.database import get_db, init_db
try:
    db = next(get_db())
    db.execute('SELECT 1')
    print('✅ 数据库连接成功')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
    exit(1)
"

echo "=== 数据库部署完成 ==="
EOL

    chmod +x deploy_database.sh
    echo -e "${GREEN}部署脚本创建完成${NC}"
}

# 主函数
main() {
    check_env
    install_deps
    create_postgres_config
    create_migration
    create_supabase_config
    create_deploy_script
    
    echo -e "${GREEN}=== 数据库配置完成 ==="
    echo -e "请运行 ./deploy_database.sh 来选择并配置数据库平台"
}

# 运行主函数
main "$@"
