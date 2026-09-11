<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\Process\Process;

class CertificateEditorController extends Controller
{
    public function template(): JsonResponse
    {
        $template = json_decode(file_get_contents(base_path('../resources/hof-template.json')), true, flags: JSON_THROW_ON_ERROR);
        $template['defaults']['issueDate'] = now()->format('Y-m-d');

        return response()->json($template)->header('Cache-Control', 'no-store');
    }

    public function background(): BinaryFileResponse
    {
        return response()->file(base_path('../resources/hof-background.png'), [
            'Content-Type' => 'image/png',
            'Cache-Control' => 'public, max-age=3600',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    public function preview(Request $request): JsonResponse
    {
        abort_if(strlen($request->getContent()) > 8192, 413);
        $data = $this->validatedFields($request, false);
        $result = $this->render(['action' => 'preview', 'data' => $data]);

        return response()->json($result)->header('Cache-Control', 'no-store');
    }

    public function export(Request $request): Response
    {
        abort_if(strlen($request->getContent()) > 14_100_000, 413);
        $data = $this->validatedFields($request, true);
        $format = $data['format'];
        $result = $this->render(['action' => 'export', 'format' => $format, 'data' => $data]);
        $content = base64_decode($result['content'], true);
        abort_if($content === false, 503, 'The certificate could not be generated.');
        $mime = match ($format) {
            'pdf' => 'application/pdf',
            'png' => 'image/png',
            'jpeg' => 'image/jpeg',
        };

        return response($content, 200, [
            'Content-Type' => $mime,
            'Content-Disposition' => 'attachment; filename="Certificate-of-Appreciation.'.$format.'"',
            'Cache-Control' => 'private, no-store',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    private function validatedFields(Request $request, bool $export): array
    {
        $rules = [];
        foreach (['recipientName', 'designation', 'identityLine', 'issueDate'] as $field) {
            $rules[$field] = [$export ? 'required' : 'nullable', 'string', 'max:160'];
        }
        if ($export) {
            $rules += [
                'format' => ['required', 'in:pdf,png,jpeg'],
                'profileImage' => ['required', 'string', 'max:14000000'],
                'crop' => ['required', 'array:zoom,x,y'],
                'crop.zoom' => ['required', 'numeric', 'between:1,4'],
                'crop.x' => ['required', 'numeric', 'between:-1,1'],
                'crop.y' => ['required', 'numeric', 'between:-1,1'],
            ];
        }
        $unexpected = array_diff(array_keys($request->all()), array_keys($rules));
        if ($unexpected !== []) {
            throw ValidationException::withMessages(['template' => 'Only the predefined certificate fields may be submitted.']);
        }

        return $request->validate($rules);
    }

    private function render(array $payload): array
    {
        $process = new Process([
            config('services.certificate.python', 'python'),
            base_path('../scripts/certificate_renderer.py'),
        ], base_path('..'), ['PYTHONUTF8' => '1'], json_encode($payload, JSON_THROW_ON_ERROR), 45);
        try {
            $process->run();
            $result = json_decode($process->getOutput(), true, flags: JSON_THROW_ON_ERROR);
        } catch (\Throwable $error) {
            Log::error('Certificate renderer unavailable', ['exception' => $error::class]);
            abort(503, 'The certificate renderer is unavailable. Please try again.');
        }
        if ($process->getExitCode() === 2) {
            throw ValidationException::withMessages($result['errors']);
        }
        if (! $process->isSuccessful()) {
            Log::error('Certificate rendering failed', ['exit_code' => $process->getExitCode()]);
            abort(503, 'The certificate could not be rendered. Please contact the administrator.');
        }

        return $result;
    }
}
