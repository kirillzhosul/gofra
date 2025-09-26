# IDE and Editor support

Enhance your Gofra development experience with official and unofficial extensions for your favorite code editor. 
These extensions provide syntax highlighting, code snippets, and useful commands to streamline your workflow.

## Vim / Neovim
The Gofra plugin for Vim is available on GitHub and can be easily installed.

Huge thanks to [Stepan Zubkov](https://github.com/stepanzubkov) for developing an extension!

#### Installation
Please refer to their respective documentation using the repository URL: [github.com/stepanzubkov/gofra.vim](https://github.com/stepanzubkov/gofra.vim)

#### Features

Syntax Highlighting: Support for `.gof` file syntax.

## Visual Studio Code

The extension is currently available by installing it directly from the source. We are working on publishing it to the Visual Studio Code Marketplace for easier installation.

#### Manual Installation from Source
1.Clone the Repository:
```bash
git clone https://github.com/kirillzhosul/gofra
cd gofra/editors/vscode
```

2. Package the Extension:
You need to have Node.js and the vsce (Visual Studio Code Extensions) tool installed.
```bash
npm install -g @vscode/vsce
vsce package
```
This command will create a .vsix file in the directory.

3. Install in VS Code:
- Open VS Code.
- Go to the Extensions view (Ctrl+Shift+X / Cmd+Shift+X).
- Click the "..." menu in the top-right of the Extensions panel and select Install from VSIX....
- Navigate to and select the .vsix file you created in the previous step.
- Reload VS Code when prompted.

#### Features
Syntax Highlighting: Support for `.gof` file syntax.

## Other Editors & Contributing

Support for your editor not listed here? We welcome contributions!

The source code for all editor extensions is located in the `editors` directory of the main Gofra repository or your own repository if you wish to separate that. If you'd like to create an extension for another editor (such as Sublime Text, IntelliJ IDEA, or Emacs), please use the existing implementations as a reference.

Check the `editors` directory in the [Gofra source code](https://github.com/kirillzhosul/gofra).
Feel free to open an issue on GitHub to discuss your plans for a new extension.
Submit a pull request with your new extension, and we'll be happy to include it here!