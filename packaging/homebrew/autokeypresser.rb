cask "autokeypresser" do
  version "2.0"
  sha256 "23c667f9f500b13a184fa244ef64b8fced5e3c34542be6cfc721a43f83b1d4b3"

  url "https://github.com/CamjamPNG/autokeypresser/releases/download/v#{version}/AutoKeyPresser-Portable-macos.zip"
  name "AutoKeyPresser"
  desc "Cross-platform keyboard and mouse auto presser"
  homepage "https://github.com/CamjamPNG/autokeypresser"

  app "AutoKeyPresser.app"
end
