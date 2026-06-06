// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "NeurOS",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "NeurOS", targets: ["NeurOS"])
    ],
    targets: [
        .executableTarget(
            name: "NeurOS",
            path: "Sources"
        )
    ]
)
