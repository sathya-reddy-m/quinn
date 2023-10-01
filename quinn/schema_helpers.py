from pyspark.sql import types as T
import json

def print_schema_as_code(dtype: T.DataType) -> str:
    """Represent DataType (including StructType) as valid Python code.

    :param dtype: The input DataType or Schema object
    :type dtype: pyspark.sql.types.DataType
    :return: A valid python code which generate the same schema.
    :rtype: str
    """
    res = []
    if isinstance(dtype, T.StructType):
        res.append("StructType(\n\tfields=[")
        for field in dtype.fields:
            for line in _repr_column(field).split("\n"):
                res.append("\n\t\t")
                res.append(line)
            res.append(",")
        res.append("\n\t]\n)")

    elif isinstance(dtype, T.ArrayType):
        res.append("ArrayType(")
        res.append(print_schema_as_code(dtype.elementType))
        res.append(")")

    elif isinstance(dtype, T.MapType):
        res.append("MapType(")
        res.append(f"\n\t{print_schema_as_code(dtype.keyType)},")
        for line in print_schema_as_code(dtype.valueType).split("\n"):
            res.append("\n\t")
            res.append(line)
        res.append(",")
        res.append(f"\n\t{dtype.valueContainsNull},")
        res.append("\n)")

    elif isinstance(dtype, T.DecimalType):
        res.append(f"DecimalType({dtype.precision}, {dtype.scale})")

    else:
        if str(dtype).endswith("()"):  # PySpark 3.3+
            res.append(str(dtype))
        else:
            res.append(f"{dtype}()")

    return "".join(res)


def _repr_column(column: T.StructField) -> str:
    res = []

    if (
        isinstance(column.dataType, T.StructType)
        or isinstance(column.dataType, T.ArrayType)
        or isinstance(column.dataType, T.MapType)
    ):
        res.append(f'StructField(\n\t"{column.name}",')
        for line in print_schema_as_code(column.dataType).split("\n"):
            res.append("\n\t")
            res.append(line)
        res.append(",")
        res.append(f"\n\t{column.nullable},")
        res.append("\n)")

    else:
        res.append(
            f'StructField("{column.name}", {print_schema_as_code(column.dataType)}, {column.nullable})'
        )

    return "".join(res)


def schema_from_csv(spark, file_path) -> T.StructType:
    """Return a StructType from a CSV file containing schema configuration.

    :param spark: The SparkSession object
    :type spark: pyspark.sql.session.SparkSession

    :param file_path: The path to the CSV file containing the schema configuration
    :type file_path: str

    :raises ValueError: If the CSV file does not contain the expected columns: name, type, nullable, description

    :return: A StructType object representing the schema configuration
    :rtype: pyspark.sql.types.StructType
    """
    def _validate_json(metadata: str) -> dict:
        if metadata is None:
            return {}

        try:
            metadata_dict = json.loads(metadata)

        except json.JSONDecodeError:
            raise ValueError(f'Invalid JSON: {metadata}')

        return metadata_dict

    def _lookup_type(type_str: str) -> T.DataType:
        type_lookup = {
            'string': T.StringType(),
            'int': T.IntegerType(),
            'float': T.FloatType(),
            'double': T.DoubleType(),
            'boolean': T.BooleanType(),
            'bool': T.BooleanType(),
            'timestamp': T.TimestampType(),
            'date': T.DateType(),
            'binary': T.BinaryType(),
        }

        if type_str not in type_lookup:
            raise ValueError(f'Invalid type: {type_str}. Expecting one of: {type_lookup.keys()}')

        return type_lookup[type_str]

    def _convert_nullable(null_str: str) -> bool:
        if null_str is None:
            return True
        
        parsed_val = null_str.lower()
        if parsed_val not in ['true', 'false']:
            raise ValueError(f'Invalid nullable value: {null_str}. Expecting True or False.')

        return parsed_val == 'true'

    schema_df = spark.read.csv(file_path, header=True)
    possible_columns = ['name', 'type', 'nullable', 'metadata']
    num_cols = len(schema_df.columns)
    expected_columns = possible_columns[0:num_cols]

    # ensure that csv contains the expected columns: name, type, nullable, description
    if schema_df.columns != expected_columns:
        raise ValueError(f'CSV must contain columns in this order: {expected_columns}')

    # create a StructType per field
    fields = []
    for row in schema_df.collect():
        field = T.StructField(
            name=row['name'],
            dataType=_lookup_type(row['type']),
            nullable=_convert_nullable(row['nullable']) if 'nullable' in row else True,
            metadata=_validate_json(row['metadata'] if 'metadata' in row else None)
        )
        fields.append(field)

    schema = T.StructType(fields=fields)
    return schema
