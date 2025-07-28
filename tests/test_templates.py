import tempfile
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel
from unittest.mock import patch, MagicMock

from counterpoint.templates import MessageTemplate
from counterpoint.templates.prompts_manager import PromptsManager


@pytest.fixture
def prompts_manager():
    return PromptsManager(prompts_path=Path(__file__).parent / "data" / "prompts")


async def test_message_template():
    template = MessageTemplate(
        role="user",
        content_template="Hello, {{ name }}!",
    )

    message = template.render(name="Orlande de Lassus")

    assert message.role == "user"
    assert message.content == "Hello, Orlande de Lassus!"


async def test_multi_message_template_parsing(prompts_manager):
    messages = await prompts_manager.render_template(
        "multi_message.j2",
        {
            "theory": "Normandy is actually the center of the universe because its perfect balance of rain, cheese, and cider creates a quantum field that bends space-time."
        },
    )

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert (
        "You are an impartial evaluator of scientific theories" in messages[0].content
    )


async def test_invalid_template(prompts_manager):
    with pytest.raises(ValueError):
        await prompts_manager.render_template("invalid.j2")


async def test_simple_template(prompts_manager):
    messages = await prompts_manager.render_template("simple.j2")

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert (
        messages[0].content
        == "This is a simple prompt that should be rendered as a single user message."
    )


def test_pydantic_json_rendering_inline():
    class Book(BaseModel):
        title: str
        description: str

    template = MessageTemplate(
        role="user",
        content_template="Hello, consider this content:\n{{ book }}!",
    )

    book = Book(
        title="The Great Gatsby",
        description="The Great Gatsby is a novel by F. Scott Fitzgerald.",
    )

    message = template.render(book=book)

    assert message.role == "user"
    expected_json = """{
    "title": "The Great Gatsby",
    "description": "The Great Gatsby is a novel by F. Scott Fitzgerald."
}"""
    assert message.content == f"Hello, consider this content:\n{expected_json}!"


async def test_pydantic_json_rendering_with_prompts_manager():
    class Book(BaseModel):
        title: str
        description: str

    book = Book(
        title="The Great Gatsby",
        description="The Great Gatsby is a novel by F. Scott Fitzgerald.",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        prompts_manager = PromptsManager(prompts_path=tmp_dir)

        template_path = Path(tmp_dir) / "book.j2"
        template_path.write_text("Here is a book:\n{{ book }}")

        messages = await prompts_manager.render_template("book.j2", {"book": book})

        assert len(messages) == 1
        assert messages[0].role == "user"
        expected_json = """{
    "title": "The Great Gatsby",
    "description": "The Great Gatsby is a novel by F. Scott Fitzgerald."
}"""
        assert messages[0].content == f"Here is a book:\n{expected_json}"


class TestPromptsManager:
    def test_register_prompts_source(self):
        manager = PromptsManager()
        manager.register_prompts_source("/path/to/prompts", "test")
        assert manager.prompts_sources["test"] == Path("/path/to/prompts")

    def test_register_prompts_source_warning(self):
        manager = PromptsManager()
        manager.register_prompts_source("/path/to/prompts", "test")
        
        with pytest.warns(UserWarning, match="Prompt source test already registered"):
            manager.register_prompts_source("/another/path", "test")

    @pytest.mark.parametrize("namespace,expected_error", [
        ("namespace with spaces", "Invalid namespace format"),
        ("", "Empty namespace not allowed"),
        ("namespace/with/slashes", "Invalid namespace format"),
    ])
    def test_register_prompts_source_invalid_namespace(self, namespace, expected_error):
        manager = PromptsManager()
        
        with pytest.raises(ValueError, match=expected_error):
            manager.register_prompts_source("/path/to/prompts", namespace)

    def test_set_prompts_path(self):
        manager = PromptsManager()
        manager.set_prompts_path("/custom/prompts")
        assert manager.prompts_path == Path("/custom/prompts")

    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    def test_resolve_package_namespace_success(self, mock_import):
        manager = PromptsManager()
        
        # Mock the module
        mock_module = MagicMock()
        mock_module.__file__ = "/path/to/package/__init__.py"
        mock_import.return_value = mock_module
        
        # Mock the prompts directory exists
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                result = manager._resolve_package_namespace("test_package")
                
        assert result == Path("/path/to/package/prompts")
        mock_import.assert_called_once_with("test_package")

    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    def test_resolve_package_namespace_import_error(self, mock_import):
        manager = PromptsManager()
        
        # Mock import error
        mock_import.side_effect = ImportError("No module named 'test_package'")
        
        result = manager._resolve_package_namespace("test_package")
        assert result is None

    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    def test_resolve_package_namespace_no_prompts_dir(self, mock_import):
        manager = PromptsManager()
        
        # Mock the module
        mock_module = MagicMock()
        mock_module.__file__ = "/path/to/package/__init__.py"
        mock_import.return_value = mock_module
        
        # Mock the prompts directory doesn't exist
        with patch.object(Path, 'exists', return_value=False):
            result = manager._resolve_package_namespace("test_package")
            
        assert result is None

    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    def test_resolve_package_namespace_file_module(self, mock_import):
        manager = PromptsManager()
        
        # Mock a single-file module
        mock_module = MagicMock()
        mock_module.__file__ = "/path/to/package.py"
        mock_import.return_value = mock_module
        
        # Mock the prompts directory exists
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                result = manager._resolve_package_namespace("test_package")
                
        assert result == Path("/path/to/prompts")

    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    def test_resolve_submodule_namespace(self, mock_import):
        manager = PromptsManager()
        
        # Mock a submodule (e.g., lidar.probes)
        mock_module = MagicMock()
        mock_module.__file__ = "/path/to/lidar/probes/__init__.py"
        mock_import.return_value = mock_module
        
        # Mock the prompts directory exists
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                result = manager._resolve_package_namespace("lidar.probes")
                
        assert result == Path("/path/to/lidar/probes/prompts")
        mock_import.assert_called_once_with("lidar.probes")



    @patch('counterpoint.templates.prompts_manager.importlib.import_module')
    async def test_render_template_with_unresolvable_submodule_namespace(self, mock_import):
        manager = PromptsManager()
        
        # Mock import error for submodule
        mock_import.side_effect = ImportError("No module named 'lidar.probes'")
        
        with pytest.raises(ValueError, match="Prompt source lidar.probes not registered and package not found"):
            await manager.render_template("lidar.probes::test_template.j2")

    def test_thread_safety_concurrent_registration(self):
        """Test that concurrent registration operations are thread-safe."""
        manager = PromptsManager()
        results = []
        errors = []
        
        def register_source(namespace, source):
            try:
                manager.register_prompts_source(source, namespace)
                results.append((namespace, source))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads trying to register sources concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=register_source, 
                args=(f"namespace_{i}", f"/path/to/source_{i}")
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred and all registrations succeeded
        assert len(errors) == 0
        assert len(results) == 10
        assert len(manager.prompts_sources) == 10
        
        # Verify all namespaces are properly registered
        for i in range(10):
            assert f"namespace_{i}" in manager.prompts_sources
            assert manager.prompts_sources[f"namespace_{i}"] == Path(f"/path/to/source_{i}")

    def test_thread_safety_concurrent_read_write(self):
        """Test that concurrent read and write operations are thread-safe."""
        manager = PromptsManager()
        read_results = []
        write_results = []
        errors = []
        
        def register_source(namespace, source):
            try:
                manager.register_prompts_source(source, namespace)
                write_results.append((namespace, source))
            except Exception as e:
                errors.append(e)
        
        def read_source(namespace):
            try:
                # Simulate reading from prompts_sources
                if namespace in manager.prompts_sources:
                    result = manager.prompts_sources[namespace]
                    read_results.append((namespace, result))
            except Exception as e:
                errors.append(e)
        
        # Create mixed read/write operations
        threads = []
        for i in range(5):
            # Write thread
            write_thread = threading.Thread(
                target=register_source, 
                args=(f"namespace_{i}", f"/path/to/source_{i}")
            )
            threads.append(write_thread)
            
            # Read thread (will read existing or newly written data)
            read_thread = threading.Thread(
                target=read_source, 
                args=(f"namespace_{i % 3}",)  # Read from earlier namespaces
            )
            threads.append(read_thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0
        assert len(write_results) == 5

    @pytest.mark.parametrize("exception,expected_warning", [
        (ImportError("No module named 'test_package'"), "Package test_package not found"),
        (PermissionError("Permission denied"), "Error resolving package test_package: Permission denied"),
        (FileNotFoundError("File not found"), "Error resolving package test_package: File not found"),
        (RuntimeError("Runtime error"), "Error resolving package test_package: Runtime error"),
    ])
    @patch('counterpoint.templates.prompts_manager.importlib.import_module')  
    def test_warning_on_namespace_resolution_errors(self, mock_import, exception, expected_warning):
        """Test that warnings are properly emitted on various errors during namespace resolution."""
        manager = PromptsManager()
        
        mock_import.side_effect = exception
        
        with pytest.warns(UserWarning, match=expected_warning):
            result = manager._resolve_package_namespace("test_package")
            
        assert result is None

    async def test_render_template_explicit_registration_fallback(self):
        """Test that explicit registration takes precedence over auto-resolution."""
        manager = PromptsManager()
        
        # Explicitly register a namespace
        manager.register_prompts_source("/explicit/path", "test_package")
        
        with patch('counterpoint.templates.prompts_manager.create_message_environment') as mock_env:
            mock_template = MagicMock()
            mock_env.return_value.get_template.return_value = mock_template
            
            # Make render_async return a coroutine
            async def mock_render_async(variables):
                return ""
            mock_template.render_async = mock_render_async
            mock_template.environment._collected_messages = []
            
            await manager.render_template("test_package::template.j2")
            
            # Verify it used the explicit path, not auto-resolution
            mock_env.assert_called_once_with("/explicit/path")

    @pytest.mark.parametrize("template_name,expected_error", [
        ("::template.j2", "Empty namespace not allowed"),
        ("namespace with spaces::template.j2", "Invalid namespace format"),
        ("namespace/with/slashes::template.j2", "Invalid namespace format"),
    ])
    async def test_malformed_namespace_syntax(self, template_name, expected_error):
        """Test handling of malformed namespace syntax."""
        manager = PromptsManager()
        
        with pytest.raises(ValueError, match=expected_error):
            await manager.render_template(template_name)

    @pytest.mark.parametrize("namespace", [
        "simple",
        "package.module", 
        "package_name",
        "package-name",
        "package123",
        "123package",
        "_private",
        "a.b.c.d",
        "namespace123"
    ])
    async def test_valid_namespace_formats(self, namespace):
        """Test that valid namespace formats don't raise format errors."""
        manager = PromptsManager()
        
        with pytest.raises(ValueError) as exc_info:
            await manager.render_template(f"{namespace}::template.j2")
        
        # Should fail because namespace is not registered, not because of format
        assert "Invalid namespace format" not in str(exc_info.value), f"Namespace {namespace} should be valid format"
        assert "not registered and package not found" in str(exc_info.value)

    @pytest.mark.parametrize("source_path,namespace,expected_path", [
        ("./relative/path", "test", Path("./relative/path")),
        ("/some/../normalized/path", "test2", Path("/some/../normalized/path")),
        ("/absolute/path", "test3", Path("/absolute/path")),
        ("relative/path", "test4", Path("relative/path")),
    ])
    def test_path_normalization_in_registration(self, source_path, namespace, expected_path):
        """Test that paths are properly handled during registration."""
        manager = PromptsManager()
        
        manager.register_prompts_source(source_path, namespace)
        assert manager.prompts_sources[namespace] == expected_path
