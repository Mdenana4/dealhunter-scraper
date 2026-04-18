import 'package:dio/dio.dart';

class ApiClient {
  late final Dio _dio;
  final String baseUrl;
  String? _lastError;
  bool _isConnected = false;

  String? get lastError => _lastError;
  bool get isConnected => _isConnected;

  ApiClient({
    this.baseUrl = 'https://dealhunter-scraper.onrender.com',
  }) {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        contentType: 'application/json',
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          print('→ [API] ${options.method.toUpperCase()} ${options.path}');
          if (options.queryParameters.isNotEmpty) {
            print('  Query: ${options.queryParameters}');
          }
          if (options.data != null) {
            print('  Data: ${options.data}');
          }
          return handler.next(options);
        },
        onResponse: (response, handler) {
          _isConnected = true;
          _lastError = null;
          print('✓ [API] Response ${response.statusCode} from ${response.requestOptions.path}');
          return handler.next(response);
        },
        onError: (error, handler) {
          _isConnected = false;
          _lastError = error.message ?? 'Unknown error';
          print('✗ [API ERROR] ${error.type}');
          print('  Message: ${error.message}');
          print('  Status: ${error.response?.statusCode}');
          print('  Response: ${error.response?.data}');
          return handler.next(error);
        },
      ),
    );
    print('✓ [API] Client initialized with baseUrl: $baseUrl');
  }

  Dio get dio => _dio;

  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    return _dio.get<T>(
      path,
      queryParameters: queryParameters,
    );
  }

  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
  }) async {
    return _dio.post<T>(path, data: data);
  }

  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
  }) async {
    return _dio.put<T>(path, data: data);
  }

  Future<Response<T>> delete<T>(String path) async {
    return _dio.delete<T>(path);
  }

  Future<bool> testConnection() async {
    try {
      print('\n🔍 [API] Testing connection to $baseUrl...');
      final response = await get('/health');
      print('✓ [API] Connection successful: ${response.statusCode}');
      _isConnected = true;
      _lastError = null;
      return true;
    } catch (e) {
      _isConnected = false;
      _lastError = e.toString();
      print('✗ [API] Connection failed: $e');
      return false;
    }
  }
}
