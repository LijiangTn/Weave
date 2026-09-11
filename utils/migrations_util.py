"""
@项目名: voice-cloning-backend
@文 件: migrations.py
@作 者: 努尔艾力·艾则孜
@日 期: 2025-11-08
@详 细: 数据库迁移工具，用于在项目启动时自动执行数据库结构变更
        支持自动对比模型定义和数据库实际结构，自动生成并执行迁移SQL
"""

from typing import Dict, List, Set, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, DateTime, String, Integer, Text, Boolean, Enum as SQLEnum, Float, DECIMAL, BigInteger, Date, Time, JSON
from sqlalchemy.sql.sqltypes import TypeEngine
from config.database import Base
from utils.log_util import logger

class DatabaseMigration:
    """数据库迁移管理类 - 自动对比模型和数据库结构并执行迁移"""

    @staticmethod
    async def get_database_columns(db: AsyncSession, table_name: str) -> Dict[str, Dict[str, Any]]:
        """
        获取数据库表中已存在的所有字段信息
        
        :param db: 数据库会话
        :param table_name: 表名
        :return: 字段信息字典 {字段名: {type, nullable, default, comment}}
        """
        try:
            query = text("""
                SELECT 
                    COLUMN_NAME as name,
                    COLUMN_TYPE as type,
                    IS_NULLABLE as nullable,
                    COLUMN_DEFAULT as `default`,
                    COLUMN_COMMENT as comment,
                    EXTRA as extra
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table_name
            """)
            result = await db.execute(query, {"table_name": table_name})
            columns = {}
            for row in result:
                columns[row.name] = {
                    "type": row.type,
                    "nullable": row.nullable == "YES",
                    "default": row.default,
                    "comment": row.comment or "",
                    "extra": row.extra or ""
                }
            return columns
        except Exception as e:
            logger.error(f"获取数据库字段信息失败 table: {table_name}, 错误: {str(e)}")
            return {}

    @staticmethod
    async def get_database_indexes(db: AsyncSession, table_name: str) -> Set[str]:
        """
        获取数据库表中已存在的所有索引名称
        
        :param db: 数据库会话
        :param table_name: 表名
        :return: 索引名称集合
        """
        try:
            query = text("""
                SELECT DISTINCT INDEX_NAME
                FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table_name
                AND INDEX_NAME != 'PRIMARY'
            """)
            result = await db.execute(query, {"table_name": table_name})
            return {row.INDEX_NAME for row in result}
        except Exception as e:
            logger.error(f"获取数据库索引信息失败 table: {table_name}, 错误: {str(e)}")
            return set()

    @staticmethod
    def get_sql_type(column_type: TypeEngine) -> str:
        """
        将SQLAlchemy类型转换为MySQL类型
        
        :param column_type: SQLAlchemy列类型
        :return: MySQL类型字符串
        """
        if isinstance(column_type, String):
            length = getattr(column_type, 'length', 255)
            return f"VARCHAR({length})"
        elif isinstance(column_type, Text):
            return "TEXT"
        elif isinstance(column_type, BigInteger):
            return "BIGINT"
        elif isinstance(column_type, Integer):
            return "INT"
        elif isinstance(column_type, Boolean):
            return "TINYINT(1)"
        elif isinstance(column_type, DateTime):
            return "DATETIME"
        elif isinstance(column_type, Date):
            return "DATE"
        elif isinstance(column_type, Time):
            return "TIME"
        elif isinstance(column_type, Float):
            return "FLOAT"
        elif isinstance(column_type, DECIMAL):
            precision = getattr(column_type, 'precision', 10)
            scale = getattr(column_type, 'scale', 2)
            return f"DECIMAL({precision},{scale})"
        elif isinstance(column_type, JSON):
            return "JSON"
        elif isinstance(column_type, SQLEnum):
            # 处理枚举类型
            enum_values = [f"'{v.value}'" if hasattr(v, 'value') else f"'{v}'" for v in column_type.enums]
            return f"ENUM({','.join(enum_values)})"
        else:
            return "VARCHAR(255)"

    @staticmethod
    def build_column_definition(column_name: str, column) -> str:
        """
        构建列定义的SQL片段
        
        :param column_name: 字段名
        :param column: SQLAlchemy列对象
        :return: 列定义SQL
        """
        sql_parts = [f"`{column_name}`"]
        
        # 字段类型
        sql_type = DatabaseMigration.get_sql_type(column.type)
        sql_parts.append(sql_type)
        
        # 是否允许NULL
        if column.nullable:
            sql_parts.append("NULL")
        else:
            sql_parts.append("NOT NULL")
        
        # 默认值
        if column.default is not None:
            default_value = column.default
            if hasattr(default_value, 'arg'):
                # 处理函数默认值（如 datetime.now）
                if 'datetime.now' in str(default_value.arg) or 'func.now' in str(default_value.arg):
                    sql_parts.append("DEFAULT CURRENT_TIMESTAMP")
                elif isinstance(default_value.arg, bool):
                    sql_parts.append(f"DEFAULT {1 if default_value.arg else 0}")
                elif isinstance(default_value.arg, (int, float)):
                    sql_parts.append(f"DEFAULT {default_value.arg}")
                elif isinstance(default_value.arg, str):
                    sql_parts.append(f"DEFAULT '{default_value.arg}'")
            elif hasattr(default_value, 'name'):
                # 处理枚举默认值
                enum_value = default_value.name if hasattr(default_value.name, 'value') else str(default_value.name)
                sql_parts.append(f"DEFAULT '{enum_value}'")
        elif not column.nullable and isinstance(column.type, DateTime):
            # 如果是 NOT NULL 的 DATETIME 字段但没有显式默认值，添加 CURRENT_TIMESTAMP
            sql_parts.append("DEFAULT CURRENT_TIMESTAMP")
        
        # ON UPDATE (针对 updated_at 字段)
        if column_name == 'updated_at' and isinstance(column.type, DateTime):
            if column.onupdate is not None:
                sql_parts.append("ON UPDATE CURRENT_TIMESTAMP")
        
        # 注释
        if column.comment:
            sql_parts.append(f"COMMENT '{column.comment}'")
        
        return " ".join(sql_parts)

    @staticmethod
    async def check_table_exists(db: AsyncSession, table_name: str) -> bool:
        """
        检查表是否存在
        
        :param db: 数据库会话
        :param table_name: 表名
        :return: 表是否存在
        """
        try:
            query = text("""
                SELECT COUNT(*) as count
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table_name
            """)
            result = await db.execute(query, {"table_name": table_name})
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"检查表是否存在失败 table: {table_name}, 错误: {str(e)}")
            return False

    @staticmethod
    async def check_need_migration(db: AsyncSession, table_name: str, model_class) -> bool:
        """
        检查表是否需要迁移（快速检查，不执行实际迁移）
        
        :param db: 数据库会话
        :param table_name: 表名
        :param model_class: SQLAlchemy模型类
        :return: 是否需要迁移
        """
        try:
            # 表不存在则不需要迁移（由 create_all 处理）
            if not await DatabaseMigration.check_table_exists(db, table_name):
                return False
            
            # 检查是否有缺失的字段
            db_columns = await DatabaseMigration.get_database_columns(db, table_name)
            db_column_names = set(db_columns.keys())
            
            model_column_names = set(model_class.__table__.columns.keys())
            
            # 如果有缺失字段，需要迁移
            if model_column_names - db_column_names:
                return True
            
            # 检查是否有缺失的索引
            db_indexes = await DatabaseMigration.get_database_indexes(db, table_name)
            
            model_indexes = set()
            if hasattr(model_class.__table__, 'indexes'):
                model_indexes = {index.name for index in model_class.__table__.indexes}
            
            # 如果有缺失索引，需要迁移
            if model_indexes - db_indexes:
                return True
            
            return False
        except Exception as e:
            logger.error(f"检查迁移需求失败 {table_name}: {str(e)}")
            return False

    @staticmethod
    async def migrate_table(db: AsyncSession, table_name: str, model_class) -> bool:
        """
        迁移单个表，自动添加缺失的字段和索引
        
        :param db: 数据库会话
        :param table_name: 表名
        :param model_class: SQLAlchemy模型类
        :return: 迁移是否成功
        """
        try:
            # 检查表是否存在
            if not await DatabaseMigration.check_table_exists(db, table_name):
                return True
            
            # 获取数据库中已有的字段
            db_columns = await DatabaseMigration.get_database_columns(db, table_name)
            db_column_names = set(db_columns.keys())
            
            # 获取模型定义的字段
            model_columns = {}
            for column_name, column in model_class.__table__.columns.items():
                model_columns[column_name] = column
            model_column_names = set(model_columns.keys())
            
            # 找出需要添加的字段
            columns_to_add = model_column_names - db_column_names
            
            if columns_to_add:
                logger.info(f"添加 {len(columns_to_add)} 个字段到 {table_name}")
                
                # 逐个添加字段
                for column_name in columns_to_add:
                    column = model_columns[column_name]
                    column_def = DatabaseMigration.build_column_definition(column_name, column)
                    
                    alter_sql = text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
                    
                    try:
                        await db.execute(alter_sql)
                        await db.commit()
                        logger.info(f"  ✓ {column_name}")
                    except Exception as e:
                        logger.error(f"  ✗ {column_name} 失败: {str(e)}")
                        await db.rollback()
                        continue
            
            # 处理索引
            await DatabaseMigration.migrate_indexes(db, table_name, model_class)
            
            return True
        except Exception as e:
            logger.error(f"迁移表失败 {table_name}: {str(e)}")
            await db.rollback()
            return False

    @staticmethod
    async def migrate_indexes(db: AsyncSession, table_name: str, model_class) -> bool:
        """
        迁移表索引，自动添加缺失的索引
        
        :param db: 数据库会话
        :param table_name: 表名
        :param model_class: SQLAlchemy模型类
        :return: 迁移是否成功
        """
        try:
            # 获取数据库中已有的索引
            db_indexes = await DatabaseMigration.get_database_indexes(db, table_name)
            
            # 获取模型定义的索引
            model_indexes = {}
            if hasattr(model_class.__table__, 'indexes'):
                for index in model_class.__table__.indexes:
                    model_indexes[index.name] = index
            
            # 找出需要添加的索引
            indexes_to_add = set(model_indexes.keys()) - db_indexes
            
            if indexes_to_add:
                logger.info(f"添加 {len(indexes_to_add)} 个索引到 {table_name}")
                
                for index_name in indexes_to_add:
                    index = model_indexes[index_name]
                    columns = [col.name for col in index.columns]
                    columns_str = ", ".join(columns)
                    
                    create_index_sql = text(f"CREATE INDEX {index_name} ON {table_name}({columns_str})")
                    
                    try:
                        await db.execute(create_index_sql)
                        await db.commit()
                        logger.info(f"  ✓ {index_name}")
                    except Exception as e:
                        logger.error(f"  ✗ {index_name} 失败: {str(e)}")
                        await db.rollback()
                        continue
            
            return True
        except Exception as e:
            logger.error(f"迁移索引失败 {table_name}: {str(e)}")
            return False

    @staticmethod
    async def run_all_migrations(db: AsyncSession) -> bool:
        """
        自动执行所有表的数据库迁移

        :param db: 数据库会话
        :return: 迁移是否全部成功
        """
        # ponytail: SQLite 用 create_all 即可, information_schema 是 MySQL 专属,
        # 跑非 MySQL 时直接跳过
        from config.env import DataBaseConfig
        if (DataBaseConfig.db_type or '').lower() != 'mysql':
            logger.info(f'DatabaseMigration: skip (db_type={DataBaseConfig.db_type})')
            return True

        all_success = True
        has_migrations = False
        
        # 遍历所有注册的模型类
        for mapper in Base.registry.mappers:
            model_class = mapper.class_
            
            # 跳过没有 __tablename__ 的类
            if not hasattr(model_class, '__tablename__'):
                continue
                
            table_name = model_class.__tablename__
            
            # 检查是否需要迁移
            need_migration = await DatabaseMigration.check_need_migration(db, table_name, model_class)
            
            if need_migration:
                if not has_migrations:
                    logger.info("=" * 60)
                    logger.info("开始执行数据库迁移...")
                    logger.info("=" * 60)
                    has_migrations = True
                
                logger.info(f"正在迁移表: {table_name}")
                success = await DatabaseMigration.migrate_table(db, table_name, model_class)
                
                if not success:
                    logger.error(f"✗ {table_name} 迁移失败")
                    all_success = False
                else:
                    logger.info(f"✓ {table_name} 迁移成功")

        if has_migrations:
            logger.info("=" * 60)
            if all_success:
                logger.info("✓ 数据库迁移全部完成")
            else:
                logger.warning("⚠ 部分迁移失败，请检查日志")
            logger.info("=" * 60)
        else:
            logger.info("数据库结构已是最新，无需迁移")

        return all_success
