cask "autokeypresser" do
  version "1.5"
  sha256 "REPLACE_WITH_RELEASE_SHA256"

  url "https://github.com/CamjamPNG/autokeypresser/releases/download/v#{version}/AutoKeyPresser-Portable-macos.zip"
  name "AutoKeyPresser"
  desc "Cross-platform keyboard and mouse auto presser"
  homepage "https://github.com/CamjamPNG/autokeypresser"

  app "AutoKeyPresser.app"
end
