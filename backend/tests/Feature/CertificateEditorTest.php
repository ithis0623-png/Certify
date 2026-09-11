<?php

namespace Tests\Feature;

use Tests\TestCase;

class CertificateEditorTest extends TestCase
{
    public function test_editor_has_only_the_controlled_inputs_and_csrf_token(): void
    {
        $this->get('/')->assertOk()->assertSee('id="recipientName"', false)
            ->assertSee('id="identityLine"', false)
            ->assertDontSee('__CSRF_TOKEN__')
            ->assertDontSee('contenteditable=')
            ->assertDontSee('appreciation-wording');
    }

    public function test_template_geometry_is_portrait_a4(): void
    {
        $this->getJson('/editor/template')->assertOk()
            ->assertJsonPath('id', 'hof-appreciation-v1')
            ->assertJsonCount(4, 'fields')
            ->assertJsonPath('image.x', 247.9955);
    }

    public function test_preview_renders_reference_text(): void
    {
        $this->postJson('/editor/preview', [
            'recipientName' => 'Hernán Simó', 'designation' => 'Digital Artist',
            'identityLine' => 'Hernán Simó Digital Art', 'issueDate' => '2026-05-05',
        ])->assertOk()->assertJsonPath('fitted.issueDate.text', '5th May, 2026')
            ->assertJsonPath('fitted.recipientName.text', 'HERNÁN SIMÓ');
    }

    public function test_locked_template_properties_are_rejected(): void
    {
        $this->postJson('/editor/preview', ['appreciationWording' => 'Changed'])
            ->assertUnprocessable()->assertJsonValidationErrors('template');
        $this->postJson('/editor/export', ['templatePath' => '/etc/passwd'])
            ->assertUnprocessable()->assertJsonValidationErrors('template');
    }

    public function test_export_requires_all_fields_and_bounded_crop(): void
    {
        $this->postJson('/editor/export', [])->assertUnprocessable()
            ->assertJsonValidationErrors(['recipientName', 'designation', 'identityLine', 'issueDate', 'profileImage']);
        $this->postJson('/editor/export', [
            'recipientName' => 'Name', 'designation' => 'Artist', 'identityLine' => 'Studio',
            'issueDate' => '2026-05-05', 'profileImage' => 'invalid', 'format' => 'pdf',
            'crop' => ['zoom' => 100, 'x' => 0, 'y' => 0],
        ])->assertUnprocessable()->assertJsonValidationErrors('crop.zoom');
    }
}
