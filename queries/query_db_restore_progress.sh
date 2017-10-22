#!/bin/sh

while :
do
	progress=$(docker exec -it nervous_goodall /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'cubsWIN:)' -h-1 -Q "SET NOCOUNT ON;SELECT cast(percent_complete as int) FROM sys.dm_exec_requests r WHERE r.command='RESTORE DATABASE'" | sed 's/[^0-9]*//g')
	if [ $progress -lt "100" ]; then
	docker exec -it nervous_goodall /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'cubsWIN:)' -Q "SET NOCOUNT ON;SELECT start_time,cast(percent_complete as int) as progress,dateadd(second,estimated_completion_time/1000, getdate()) as estimated_completion_time, cast(estimated_completion_time/1000/60 as int) as minutes_left FROM sys.dm_exec_requests r WHERE r.command='RESTORE DATABASE'"
	else 
		break
	fi
   	sleep 60
done
