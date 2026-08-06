   Set-Content -Path ".\restart-local-postgres.ps1" -Value @'
   param(
       [ValidateSet("stop","start","restart")]
       [string]$Action = "restart",
       [string]$ServiceName = "postgresql-x64-14"
   )

   function Ensure-ServiceExists {
       param([string]$Name)
       $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
       if (-not $svc) {
           Write-Error "Service '$Name' not found. Run 'Get-Service *postgres*' to see available names."
           exit 1
       }
       return $svc
   }

   function Stop-Postgres {
       param([string]$Name)
       $svc = Ensure-ServiceExists -Name $Name
       if ($svc.Status -eq "Stopped") {
           Write-Host "Service '$Name' is already stopped."
           return
       }
       Write-Host "Stopping PostgreSQL service '$Name'..."
       Stop-Service -Name $Name -Force -ErrorAction Stop
       Write-Host "Service stopped."
   }

   function Start-Postgres {
       param([string]$Name)
       $svc = Ensure-ServiceExists -Name $Name
       if ($svc.Status -eq "Running") {
           Write-Host "Service '$Name' is already running."
           return
       }
       Write-Host "Starting PostgreSQL service '$Name'..."
       Start-Service -Name $Name -ErrorAction Stop
       Write-Host "Service started."
   }

   switch ($Action) {
       "stop"    { Stop-Postgres -Name $ServiceName }
       "start"   { Start-Postgres -Name $ServiceName }
       "restart" {
           Stop-Postgres -Name $ServiceName
           Start-Postgres -Name $ServiceName
       }
   }
   '@