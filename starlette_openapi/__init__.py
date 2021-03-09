from starlette.responses import JSONResponse
from starlette.applications import Starlette
from starlette_pydantic import PydanticEndpoint, BaseForm
from pydantic import BaseModel
from pydantic.schema import get_model_name_map, schema
import simplejson


class OpenApiObj(object):
    fixed_fields = []

    def dict(self):
        result = {}
        for field in self.fixed_fields:
            if not hasattr(self, field):
                continue

            value = getattr(self, field)
            if value is None:
                continue

            if isinstance(value, OpenApiObj):
                value = value.dict()

            elif isinstance(value, list):
                tmp_value = []
                for a in value:
                    if isinstance(a, OpenApiObj):
                        tmp_value.append(a.dict())
                    else:
                        tmp_value.append(a)
                value = tmp_value
            elif isinstance(value, dict):
                tmp_value = {}
                for k, v in value.items():
                    if isinstance(v, OpenApiObj):
                        tmp_value[k] = v.dict()
                    else:
                        tmp_value[k] = v
                value = tmp_value

            if field == "ref":
                field = '$ref'
            elif field == 'location_in':
                field = "in"

            result[field] = value
        return result

    def json(self):
        return simplejson.dumps(self.dict())


class OpenApiData(OpenApiObj):
    fixed_fields = ['openapi', 'info', 'servers', 'paths', 'components', 'security', 'tags', 'externalDocs']

    def __init__(self, openapi, info, paths, components=None):
        self.openapi = openapi or "3.0.3"
        self.info = info
        self.servers = None
        self.paths = paths
        self.components = components
        self.security = []
        self.tags = []
        self.externalDocs = None


class OpenApiInfo(OpenApiObj):
    fixed_fields = ['title', 'description', 'termsOfService', 'contact', 'license', 'version']

    def __init__(self, title, version, description="", contact=None, license=None):
        self.title = title
        self.description = description
        self.termsOfService = None
        self.contact = contact
        self.license = license
        self.version = version


class OpenApiSecuritySchema(OpenApiObj):
    fixed_fields = ["type", "description", "name", "location_in", "scheme", "bearerFormat", "flows", "openIdConnectUrl"]

    def __init__(self):
        self.type = None
        self.description = None
        self.name = None
        self.location_in = None
        self.schema = None
        self.bearerFormat = None
        self.flows = None
        self.openIdConnectUrl = None


class OpenApiComponents(OpenApiObj):
    fixed_fields = ['schemas', 'responses', 'parameters', 'examples', 'requestBodies',
                    'headers', 'securitySchemes', 'links', 'callbacks']

    def __init__(self):
        self.schemas = {}
        self.responses = {}
        self.parameters = {}
        self.examples = {}
        self.requestBodies = {}
        self.headers = {}
        self.securitySchemes = {}
        self.links = {}
        self.callbacks = {}

    def set_schemas(self, schemas: dict):
        self.schemas = schemas

    def add_security_schemas(self, name, security_schema: OpenApiSecuritySchema):
        self.securitySchemes[name] = security_schema


class OpenApiOperationParameter(OpenApiObj):
    fixed_fields = ['name', 'location_in', 'description', 'required', 'deprecated', 'allowEmptyValue', 'type']

    def __init__(self, name, location_in, required, description=None, deprecated=None, allowEmptyValue=None):
        self.name = name
        self.location_in = location_in
        self.required = required
        self.description = description
        self.deprecated = deprecated
        self.allowEmptyValue = allowEmptyValue
        self.type = None


class OpenApiOperationRequest(OpenApiObj):
    fixed_fields = ['description', 'required', 'content']

    def __init__(self, required=True, description=None):
        self.content = {}
        self.required = required
        self.description = description

    def add_schema_content(self, media_type, schema_name, examples=None):
        self.content[media_type] = {
            'schema': {"$ref": "#/components/schemas/" + schema_name}
        }
        if examples:
            self.content[media_type]['examples'] = examples


class OpenApiOperationResponse(OpenApiObj):
    fixed_fields = ['description', 'headers', 'content', 'links']

    def __init__(self, description, headers=None, content=None, links=None):
        self.description = description
        self.header = headers or {}
        self.content = content or {}
        self.links = links or {}

    def add_schema_content(self, media_type, schema_name, examples=None):
        self.content[media_type] = {
            'schema': {"$ref": "#/components/schemas/" + schema_name}
        }
        if examples:
            self.content[media_type]['examples'] = examples


class OpenApiOperationSeucirty(OpenApiObj):

    def __init__(self, name, scopes=None):
        self.name = name
        self.scopes = scopes or []

    def dict(self):
        return {self.name: self.scopes}


class OpenApiOperation(OpenApiObj):
    fixed_fields = ['tags', 'consumes', 'produces', 'summary', 'description', 'externalDocs', 'operationId',
                    'parameters', 'requestBody', 'responses', 'callbacks', 'deprecated', 'security', 'servers']

    def __init__(self):
        self.tags = []
        self.summary = None
        self.description = None
        self.externalDocs = None
        self.operationId = None
        self.parameters = []
        self.requestBody = None
        self.responses = {}
        self.callbacks = None
        self.deprecated = False
        self.security = []
        self.servers = None
        self.consumes = None
        self.produces = None

    def add_parameters(self, parameter: OpenApiOperationParameter):
        self.parameters.append(parameter)

    def add_response(self, status_code, response: OpenApiOperationResponse):
        self.responses[str(status_code)] = response

    def add_security(self, security: OpenApiOperationSeucirty):
        self.security.append(security)

    def set_request_body(self, request_body: OpenApiOperationRequest):
        self.requestBody = request_body


class OpenApiPath(OpenApiObj):
    operations = ['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']
    other_fields = ['ref', 'summary', 'description', 'servers', 'parameters']
    fixed_fields = operations + other_fields

    def __init__(self):
        self.ref = None
        self.summary = None
        self.description = None
        self.servers = None
        self.parameters = None

    def add_operation(self, method, operation):
        setattr(self, method, operation)


class OpenApiPaths(OpenApiObj):

    def __init__(self):
        self.paths = {}

    def add_path(self, url, path: OpenApiPath):
        self.paths[url] = path

    def dict(self):
        result = {}
        for k, v in self.paths.items():
            result[k] = v.dict()
        return result


class OpenApi(object):

    def __init__(self, app: Starlette, title, description=None, api_url="/openapi", version="1.0"):
        self.app = app
        self.title = title
        self.description = description
        self.api_url = api_url
        self.version = version

        self.api_schemas = None
        self.components = []
        self.securitySchemas_index = {}
        self.token_url = None
        self.models_name = None

        self.app.add_route(self.api_url, self.get_openapi_data, include_in_schema=False)

    def is_pydantic_endpoint(self, endpoint):
        return isinstance(endpoint, type) and issubclass(endpoint, PydanticEndpoint)

    def get_models_name(self):
        models = set()
        for route in self.app.routes:
            endpoint = route.endpoint
            if not self.is_pydantic_endpoint(endpoint):
                continue

            for method in OpenApiPath.operations:
                if not hasattr(endpoint, method):
                    continue

                handler = getattr(endpoint, method)
                method_annotations = handler.__annotations__
                for ann_name, ann in method_annotations.items():
                    if isinstance(ann, type):
                        if issubclass(ann, BaseModel):
                            models.add(ann)
                        if issubclass(ann, BaseForm):
                            models.add(ann.model_cls)

        model_names = get_model_name_map(models)
        return model_names

    def get_openapi_operation(self, handler, route):
        operation = OpenApiOperation()
        operation.tags = route.endpoint.tags
        method_annotations = handler.__annotations__
        for ann_name, ann in method_annotations.items():
            if ann_name == "return":
                response = OpenApiOperationResponse(description="Success Response")
                response.add_schema_content("application/json", self.models_name[ann])
                operation.add_response(200, response)

            elif ann_name == "body":
                request_body = OpenApiOperationRequest()
                request_body.add_schema_content("application/json", self.models_name[ann])
                operation.set_request_body(request_body)

            elif ann_name == "form":
                request_body = OpenApiOperationRequest()
                request_body.add_schema_content("multipart/form-data", self.models_name[ann.model_cls])
                operation.set_request_body(request_body)

            elif ann_name in route.param_convertors:
                parameter = OpenApiOperationParameter(name=ann_name, location_in='path', required=True)
                operation.add_parameters(parameter)

            else:
                parameter = OpenApiOperationParameter(name=ann_name, location_in='query', required=False)
                operation.add_parameters(parameter)

        if hasattr(handler, 'auth_dict'):
            auth_dict = handler.auth_dict
            if auth_dict.get('auth_require'):
                operation.add_security(OpenApiOperationSeucirty(auth_dict['name']))
                if not auth_dict['name'] in self.securitySchemas_index:
                    self.securitySchemas_index[auth_dict['name']] = auth_dict

            elif auth_dict.get('token_url'):
                self.token_url = route.path

            del handler.auth_dict

        return operation

    def get_openapi_path(self, route):
        path = OpenApiPath()
        for method in OpenApiPath.operations:
            if not hasattr(route.endpoint, method):
                continue

            handler = getattr(route.endpoint, method)
            operation = self.get_openapi_operation(handler, route)
            path.add_operation(method, operation)
        return path

    def get_openapi_paths(self):
        paths = OpenApiPaths()
        for route in self.app.routes:
            if not self.is_pydantic_endpoint(route.endpoint):
                continue

            path = self.get_openapi_path(route)
            paths.add_path(route.path, path)
        return paths

    def get_openapi_components(self):
        components = OpenApiComponents()
        model_list = list(self.models_name.keys())
        schemas = schema(model_list, title='Pydantic_Schemas')['definitions']
        components.set_schemas(schemas)

        for name, security_dict in self.securitySchemas_index.items():
            security_schema = OpenApiSecuritySchema()
            security_schema.type = security_dict['auth_type']
            security_schema.flows = {
                "password": {
                    "scopes": {},
                    "tokenUrl": self.token_url
                }
            }
            components.add_security_schemas(name, security_schema)

        return components

    def get_openapi_data(self, request):

        if not self.api_schemas:
            self.models_name = self.get_models_name()
            info = OpenApiInfo(title=self.title, version=self.version, description=self.description)
            paths = self.get_openapi_paths()
            components = self.get_openapi_components()
            openapi_data = OpenApiData(openapi="3.0.3", info=info, paths=paths, components=components)
            self.api_schemas = openapi_data.dict()

        return JSONResponse(self.api_schemas)
