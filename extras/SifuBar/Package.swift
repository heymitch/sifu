// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SifuBar",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "SifuBar",
            path: "SifuBar",
            resources: [
                .copy("Info.plist"),
            ],
            linkerSettings: [
                .linkedLibrary("sqlite3"),
            ]
        ),
    ]
)
