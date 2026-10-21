# Veřejné ověřovací klíče Ubuntu Cloud Images

`ubuntu-cloudimage-keyring.gpg` obsahuje veřejné klíče z distribučního balíčku Ubuntu `ubuntu-cloudimage-keyring`. Instalátor používá tento soubor také na Debianu, kde odpovídající Ubuntu balíček nemusí být dostupný. Soukromé klíče v projektu nejsou.

Otisky veřejných klíčů:

- UEC Image Automatic Signing Key: `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`.
- Ubuntu Cloud Image Builder: `4A3CE3CD565D7EB5C810E2B97FF3F408476CF100`.

Instalátor nejdříve ověří podpis `SHA256SUMS.gpg` nad `SHA256SUMS` pomocí `gpgv`. Teprve potom kontroluje SHA-256 konkrétního staženého obrazu `jammy-server-cloudimg-amd64.img`. Neimportuje klíč automaticky z neověřeného keyserveru a nepřeskakuje ověření podpisu.

Původ a postup: [Ubuntu — ověření obrazu](https://ubuntu.com/docs/public-images/public-images-how-to/verify-image-checksum/) a [Ubuntu — artefakty cloud images](https://ubuntu.com/docs/public-images/public-images-reference/artifacts/).

Při rotaci klíčů ověř nový otisk z oficiálních zdrojů Canonicalu před aktualizací tohoto souboru.
