import Foundation

enum APIConfig {
    static let baseURL = "https://golfcoachnow.pythonanywhere.com"

    static func moduleURL(for module: GolfModule) -> String {
        baseURL + module.apiEndpoint
    }

    static func uploadURL(for module: GolfModule, deviceId: String) -> String {
        baseURL + "/upload?module=" + module.uploadModuleParam + "&device_id=" + deviceId
    }
}

enum APIError: LocalizedError {
    case invalidURL
    case requestFailed(statusCode: Int)
    case serverUnreachable
    case invalidResponse
    case fileReadError

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid API URL."
        case .requestFailed(let code): return "Request failed (HTTP \(code)). Try again."
        case .serverUnreachable: return "Backend not available. Check your connection."
        case .invalidResponse: return "Invalid response from server."
        case .fileReadError: return "Could not read video file."
        }
    }
}

final class APIClient {

    static let shared = APIClient()
    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120
        session = URLSession(configuration: config)
    }

    func uploadVideo(fileURL: URL, module: GolfModule, completion: @escaping (Result<CorrectionResponse, Error>) -> Void) {
        let deviceId = EntitlementManager.shared.deviceId
        guard let url = URL(string: APIConfig.uploadURL(for: module, deviceId: deviceId)) else {
            completion(.failure(APIError.invalidURL))
            return
        }

        guard let fileData = try? Data(contentsOf: fileURL) else {
            completion(.failure(APIError.fileReadError))
            return
        }

        let boundary = UUID().uuidString
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        let filename = fileURL.lastPathComponent
        let mime = mimeType(for: fileURL)

        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: \(mime)\r\n\r\n")
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n")

        request.httpBody = body

        session.dataTask(with: request) { data, response, error in
            self.handleResponse(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    func sendModuleData(_ scores: [String: Double], module: GolfModule, completion: @escaping (Result<CorrectionResponse, Error>) -> Void) {
        guard let url = URL(string: APIConfig.moduleURL(for: module)) else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: Any] = [
            "data": scores,
            "device_id": EntitlementManager.shared.deviceId,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        session.dataTask(with: request) { data, response, error in
            self.handleResponse(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    private func handleResponse(data: Data?, response: URLResponse?, error: Error?, completion: @escaping (Result<CorrectionResponse, Error>) -> Void) {
        if let urlError = error as? URLError,
           [.notConnectedToInternet, .cannotConnectToHost, .timedOut].contains(urlError.code) {
            completion(.failure(APIError.serverUnreachable))
            return
        }

        if let error {
            completion(.failure(error))
            return
        }

        guard let http = response as? HTTPURLResponse else {
            completion(.failure(APIError.invalidResponse))
            return
        }

        guard (200...299).contains(http.statusCode), let data else {
            completion(.failure(APIError.requestFailed(statusCode: http.statusCode)))
            return
        }

        do {
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let result = try decoder.decode(CorrectionResponse.self, from: data)
            completion(.success(result))
        } catch {
            completion(.failure(APIError.invalidResponse))
        }
    }

    // MARK: - Talk Mode

    func sendTalkRequest(text: String, module: GolfModule, completion: @escaping (Result<TalkResponse, Error>) -> Void) {
        guard let url = URL(string: APIConfig.baseURL + "/talk") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: String] = [
            "text": text,
            "module": module.uploadModuleParam,
            "device_id": EntitlementManager.shared.deviceId,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        session.dataTask(with: request) { data, response, error in
            self.handleDecodable(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    // MARK: - Auth

    func requestLoginCode(email: String, completion: @escaping (Result<Void, Error>) -> Void) {
        guard let url = URL(string: APIConfig.baseURL + "/auth/request-code") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "email": email,
            "device_id": EntitlementManager.shared.deviceId,
        ])

        session.dataTask(with: request) { _, response, error in
            if let error { completion(.failure(error)); return }
            guard let http = response as? HTTPURLResponse else {
                completion(.failure(APIError.invalidResponse)); return
            }
            if http.statusCode == 202 || http.statusCode == 200 {
                completion(.success(()))
            } else if http.statusCode == 429 {
                completion(.failure(APIError.requestFailed(statusCode: 429)))
            } else {
                completion(.failure(APIError.requestFailed(statusCode: http.statusCode)))
            }
        }.resume()
    }

    func verifyLoginCode(email: String, code: String, completion: @escaping (Result<String, Error>) -> Void) {
        guard let url = URL(string: APIConfig.baseURL + "/auth/verify-code") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "email": email,
            "code": code,
            "device_id": EntitlementManager.shared.deviceId,
        ])

        session.dataTask(with: request) { data, response, error in
            if let error { completion(.failure(error)); return }
            guard let http = response as? HTTPURLResponse, let data else {
                completion(.failure(APIError.invalidResponse)); return
            }
            if http.statusCode == 200 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let token = json["token"] as? String {
                    completion(.success(token))
                } else {
                    completion(.failure(APIError.invalidResponse))
                }
            } else {
                completion(.failure(APIError.requestFailed(statusCode: http.statusCode)))
            }
        }.resume()
    }

    func signOut(completion: @escaping (Result<Void, Error>) -> Void) {
        guard let url = URL(string: APIConfig.baseURL + "/auth/sign-out") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        if let token = AuthManager.shared.token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        session.dataTask(with: request) { _, response, error in
            if let error { completion(.failure(error)); return }
            guard let http = response as? HTTPURLResponse else {
                completion(.failure(APIError.invalidResponse)); return
            }
            if (200...299).contains(http.statusCode) {
                completion(.success(()))
            } else {
                completion(.failure(APIError.requestFailed(statusCode: http.statusCode)))
            }
        }.resume()
    }

    // MARK: - Payments

    func createCheckoutSession(deviceId: String, completion: @escaping (Result<CheckoutResponse, Error>) -> Void) {
        guard let url = URL(string: APIConfig.baseURL + "/payments/checkout-session") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["device_id": deviceId])

        session.dataTask(with: request) { data, response, error in
            self.handleDecodable(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    func checkUnlockStatus(deviceId: String, completion: @escaping (Result<UnlockStatusResponse, Error>) -> Void) {
        guard var components = URLComponents(string: APIConfig.baseURL + "/payments/unlock-status") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        components.queryItems = [URLQueryItem(name: "device_id", value: deviceId)]

        guard let url = components.url else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        if let token = AuthManager.shared.token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        session.dataTask(with: request) { data, response, error in
            self.handleDecodable(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    func checkEntitlement(deviceId: String, module: GolfModule, completion: @escaping (Result<EntitlementResponse, Error>) -> Void) {
        guard var components = URLComponents(string: APIConfig.baseURL + "/entitlement") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        components.queryItems = [
            URLQueryItem(name: "device_id", value: deviceId),
            URLQueryItem(name: "module", value: module.uploadModuleParam),
        ]

        guard let url = components.url else {
            completion(.failure(APIError.invalidURL))
            return
        }

        session.dataTask(with: URLRequest(url: url)) { data, response, error in
            self.handleDecodable(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    private func handleDecodable<T: Decodable>(data: Data?, response: URLResponse?, error: Error?, completion: @escaping (Result<T, Error>) -> Void) {
        if let urlError = error as? URLError,
           [.notConnectedToInternet, .cannotConnectToHost, .timedOut].contains(urlError.code) {
            completion(.failure(APIError.serverUnreachable))
            return
        }

        if let error {
            completion(.failure(error))
            return
        }

        guard let http = response as? HTTPURLResponse else {
            completion(.failure(APIError.invalidResponse))
            return
        }

        guard (200...299).contains(http.statusCode), let data else {
            completion(.failure(APIError.requestFailed(statusCode: http.statusCode)))
            return
        }

        do {
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let result = try decoder.decode(T.self, from: data)
            completion(.success(result))
        } catch {
            completion(.failure(APIError.invalidResponse))
        }
    }

    // MARK: - Analytics

    func trackEvent(_ name: String, module: GolfModule? = nil) {
        guard let url = URL(string: APIConfig.baseURL + "/analytics/event") else { return }

        var payload: [String: String] = [
            "device_id": EntitlementManager.shared.deviceId,
            "event_name": name,
            "platform": "ios",
        ]
        if let module { payload["module"] = module.uploadModuleParam }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        session.dataTask(with: request) { _, _, _ in }.resume()
    }

    // MARK: - Performance

    func fetchHistory(module: GolfModule, completion: @escaping (Result<PerformanceHistory, Error>) -> Void) {
        guard var components = URLComponents(string: APIConfig.baseURL + "/performance/history") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        components.queryItems = [
            URLQueryItem(name: "device_id", value: EntitlementManager.shared.deviceId),
            URLQueryItem(name: "module", value: module.uploadModuleParam),
            URLQueryItem(name: "limit", value: "20"),
        ]
        guard let url = components.url else {
            completion(.failure(APIError.invalidURL))
            return
        }
        session.dataTask(with: URLRequest(url: url)) { data, response, error in
            self.handleDecodable(data: data, response: response, error: error, completion: completion)
        }.resume()
    }

    private func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "mov": return "video/quicktime"
        case "mp4", "m4v": return "video/mp4"
        case "avi": return "video/x-msvideo"
        default: return "application/octet-stream"
        }
    }
}

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
