<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CertificateTemplate extends Model
{
    protected $fillable = ['created_by', 'name', 'background_path', 'layout', 'is_active'];

    protected function casts(): array
    {
        return ['layout' => 'array', 'is_active' => 'boolean'];
    }
}
