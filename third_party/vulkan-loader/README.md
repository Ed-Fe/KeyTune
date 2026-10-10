# Vulkan loader (`vulkan-1.dll`)

Copia redistribuível do loader Vulkan (Khronos/LunarG), versão **1.4.363.0**, x64, assinada pela LunarG.

- Origem: Vulkan Runtime (componentes) em https://vulkan.lunarg.com/ — `VulkanRT-X64-1.4.363.0-Components.zip`, pasta `x64`.
- SHA-256 do `vulkan-1.dll`: `e1fcfc9489beefa6a6d9d11d6c7517f6a2b7f16e0d3fb8f4103bee0210f314a3`
- Licença: Apache 2.0 / MIT (ver `LICENSE.txt`).

## Por que está aqui

A `libmpv-2.dll` importa funções do Vulkan 1.1+ diretamente de `vulkan-1.dll`. Em computadores com driver de vídeo antigo (por exemplo NVIDIA de 2016), o `vulkan-1.dll` de `System32` é um loader Vulkan 1.0 sem essas funções, e o Windows recusa carregar a `libmpv` (erro 127). O build copia este arquivo para a pasta `mpv` da instalação; como o Windows procura as dependências primeiro na pasta da DLL, ele passa na frente do loader do sistema. Continua usando os drivers de vídeo instalados.

Para atualizar: baixe o runtime atual na LunarG, troque o arquivo e atualize a versão e o hash acima.
