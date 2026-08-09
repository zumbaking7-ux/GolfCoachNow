import Foundation

enum APIConfig {
    static let baseURL = "https://golfcoachnow.pythonanywhere.com"
    static var wedgeURL: String { baseURL + "/wedge" }
    static var uploadURL: String { baseURL + "/upload" }
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

    func uploadVideo(fileURL: URL, completion: @escaping (Result<CorrectionResponse, Error>) -> Void) {
        guard let url = URL(string: APIConfig.uploadURL) else {
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
        }.resume()
    }

    func sendSwingData(_ scores: [String: Double], completion: @escaping (Result<CorrectionResponse, Error>) -> Void) {
        guard let url = URL(string: APIConfig.wedgeURL) else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload = ["data": scores]
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        session.dataTask(with: request) { data, response, error in
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
